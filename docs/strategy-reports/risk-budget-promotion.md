# 风险预算 Sizing 正式化决策评估报告

> 生成时间：2026-08-12 | 引擎 `pbt_v2_path_mode` | 模式 `path` | 变体 `fixed_20d`
> 主策略 `stock_candidate` 执行历史 826 行 | DuckDB `F:\MOSS-V3\data\moss.duckdb`

## 1. 执行摘要

- **等权满仓 baseline**：累计 -8.49%，最大回撤 53.70%，Sharpe -0.0101
- **风险预算 rpt=0.5%（stop_ref）**：累计 15.60%，回撤 14.18%

## 2. 引擎语义：risk_budget × gate 敞口

风险预算 sizing 与 gate 敞口为**串联约束**（`portfolio_backtest.py` L481-507）：

1. 先按 `risk_per_trade / stop_distance_pct`（ capped by `single_name_cap`）计算单票目标权重；
2. 再乘以 `day_start_equity` 得 `raw_target_amount`；
3. **剩余敞口预算** = `day_start_equity × exposure(date) - day_buy_notional`；
4. `target_amount = min(raw_target_amount, remaining_exposure_budget)`；若被截断则记 `exposure_cap_clipped`。

敞口来源优先级：每日 gate `exposure_by_date` > `exposure_by_market_state` 状态 fallback。

- 主策略 exposure_fallback_day_ratio（全窗口）：0.0378

### stop_ref 覆盖率

| 指标 | 值 |
|---|---:|
| 执行行总数 | 826 |
| 有 entry_price | 826 |
| 有 ema10_signal | 826 |
| 有效 stop_ref (entry>ema10) | 826 |
| 需 fallback (8%) | 0 |
| 有效 stop_ref 比例 | 100.0% |

## 3. 参数稳健性矩阵

### 3.1 rpt × stop 基准（全窗口 stock_candidate）

| stop_mode | rpt | cum_return | max_dd | sharpe | turnover | avg_slot | max_weight | stop_fallback_buys | exp_cap_clip | exp_fb_ratio |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stop_ref(ema10) | 0.25% | 7.95% | 7.32% | 0.8934 | 1.1674 | 0.7849 | 8.14% | 0 | 0 | 0.0378 |
| stop_ref(ema10) | 0.50% | 15.60% | 14.18% | 0.8831 | 2.3726 | 0.7849 | 15.48% | 0 | 0 | 0.0378 |
| stop_ref(ema10) | 0.75% | 22.87% | 20.60% | 0.8726 | 3.6062 | 0.7849 | 22.27% | 0 | 0 | 0.0378 |
| stop_ref(ema10) | 1.00% | 22.10% | 28.73% | 0.7116 | 4.4848 | 0.7849 | 28.20% | 0 | 2 | 0.0378 |
| stop_ref(ema10) | 1.50% | 15.68% | 42.56% | 0.4538 | 5.9415 | 0.7854 | 32.12% | 0 | 4 | 0.0378 |
| fallback(8%) | 0.25% | 5.33% | 12.11% | 0.4983 | 1.4163 | 0.7849 | 5.89% | 82 | 0 | 0.0378 |
| fallback(8%) | 0.50% | 9.91% | 23.02% | 0.4934 | 2.8099 | 0.7849 | 11.14% | 82 | 0 | 0.0378 |
| fallback(8%) | 0.75% | 13.91% | 32.66% | 0.4945 | 4.1572 | 0.7849 | 15.98% | 82 | 1 | 0.0378 |
| fallback(8%) | 1.00% | 15.48% | 41.77% | 0.4625 | 5.4356 | 0.7859 | 20.76% | 82 | 0 | 0.0378 |
| fallback(8%) | 1.50% | 9.46% | 58.98% | 0.3307 | 7.2024 | 0.7859 | 30.01% | 82 | 4 | 0.0378 |

### 3.2 等权 baseline（对照）

| cum_return | max_dd | sharpe | turnover | avg_slot | max_weight |
|---:|---:|---:|---:|---:|---:|
| -8.49% | 53.70% | -0.0101 | 5.8137 | 0.7849 | 30.18% |

### 3.3 参数悬崖检测（stop_ref 模式，相邻 rpt 步进）

- 回撤从 rpt=0.75%(20.60%) 到 rpt=1.00%(28.73%) 跳升 8.13%
- 回撤从 rpt=1.00%(28.73%) 到 rpt=1.50%(42.56%) 跳升 13.83%
- 收益从 rpt=1.00% 到 1.50% 下降 6.42%

## 4. 分窗口稳健性（等权 vs rpt=0.5% stop_ref）

| window | rows | equal_cum | equal_mdd | rb_cum | rb_mdd | delta_cum | delta_mdd | rb_sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| W1_2024-09_2025-06 | 518 | -18.29% | 37.68% | 3.67% | 9.67% | 21.96% | -28.01% | 0.4665 |
| W2_2025-07_2025-12 | 264 | -14.16% | 33.67% | 6.79% | 9.05% | 20.95% | -24.62% | 1.1876 |
| W3_2026-03_2026-06 | 44 | 28.36% | 9.53% | 8.09% | 2.36% | -20.27% | -7.17% | 3.5843 |


## 5. 跨 signal_kind 普适性（rpt=0.5% stop_ref vs 等权）

| signal_kind | rows | equal_cum | equal_mdd | rb_cum | rb_mdd | rb_sharpe | rb_better |
|---|---:|---:|---:|---:|---:|---:|---|
| uptrend_momentum | 1170 | 23.48% | 8.73% | 13.30% | 3.98% | 2.7245 | 否 |
| fresh_trend_watchlist | 1160 | 38.68% | 11.91% | 20.95% | 6.43% | 3.7595 | 否 |
| factor_screen | 1011 | -8.67% | 12.80% | -3.45% | 4.93% | -2.4760 | 是 |
| stock_candidate | 826 | -8.49% | 53.70% | 15.60% | 14.18% | 0.8831 | 是 |
| mean_reversion | 610 | 0.54% | 18.62% | 10.28% | 9.34% | 0.6035 | 是 |
| theme_breakout | 560 | 153.01% | 18.53% | 57.41% | 7.83% | 1.6614 | 否 |
| hybrid_fusion | 223 | 9.86% | 10.16% | 5.13% | 4.54% | 1.4769 | 否 |


## 6. 正式化改动面清单（仅评估，未实施）

| 层级 | 文件/模块 | 改动内容 |
|---|---|---|
| 政策 | `strategy_policy.py` | 新增 `SizingPolicy`：`default_sizing='risk_budget'`、`risk_per_trade=0.005`、`single_name_cap=0.25`、`fallback_stop_distance_pct=0.08`；扩展 `backtest_variants` 网格 |
| 引擎 | `portfolio_backtest.py` | 已支持；正式化仅需默认参数从 POLICY 读取（现状已部分实现） |
| 候选展示 | `livermore_candidate_history_service.py` / API | 输出 `position_size_hint` = `min(rpt/stop_dist, cap) × gate_exposure` |
| 前端 | `LivermorePanels.tsx` / `livermoreStrategyModel.ts` | 已有 `position_size_hint` 展示位；需接入 risk_budget 计算 |
| 实盘建议 | `market_data_livermore_service.py` 或 pretrade export | 建议仓位 API 返回 sizing 政策版本 + per-candidate weight hint |
| 回测脚本 | `scripts/run_portfolio_backtest.py` | 将 risk_budget 从 variant 扩展为默认 sizing 选项 |

## 7. 风险清单

| 风险 | 证据 | 缓解 |
|---|---|---|
| 低波动期 stop_ref 偏小 → 权重偏高 | stop_ref = (entry-ema10)/entry；窄 stop 时 raw_weight 触顶 single_name_cap(25%) | 保留 cap；监控 avg_slot 与 max_weight |
| stop_ref 缺失 fallback 8% | fallback 覆盖率见 §2；metrics.stop_ref_fallback 计数 | 补齐 history ema10；fallback 时降 rpt 或 skip |
| 高 rpt 回撤非线性放大 | 矩阵 §3：rpt 1%→1.5% 回撤跳升 | 正式参数选 0.5% 或 0.75% |
| gate 低敞口期 risk_budget 与等权差异缩小 | exposure_cap_clipped 计数；OFF/WARM 期 exposure≤0.5 | 预期行为；不需额外处理 |
| 非 stock_candidate 策略样本稀疏 | §5 各 kind 行数 | 分 kind 政策或维持等权 |

## 8. 决策建议

### 结论：**GO with caution（主策略 GO，需分 kind 验证）**

**推荐参数**：rpt = 0.5%，single_name_cap = 25%，fallback_stop = 8%，stop_mode = stop_ref(ema10)

**理由**：主策略改善显著，但子窗口或跨 kind 存在例外，建议 stock_candidate 先行。

**实施前置条件**：

1. `livermore_candidate_history` ema10 覆盖率 ≥ 90%（当前 100.0%）
2. 前端/API 输出 `position_size_hint` 与回测引擎口径一致（含 gate exposure 截断）
3. stock_candidate 正式化后观察 1-2 个 gate 周期再推广至其他 kind
4. 保留等权 shadow 对照曲线用于 drift 监控

## 附录：原始 JSON

```json
{
  "matrix": [
    {
      "cumulative_return": 0.079466,
      "max_drawdown": 0.07324,
      "daily_sharpe": 0.893384,
      "annual_turnover": 1.167358,
      "avg_slot_utilization": 0.784887,
      "max_single_name_weight": 0.081388,
      "stop_ref_fallback": 0,
      "exposure_cap_clipped": 0,
      "exposure_fallback_day_ratio": 0.037783,
      "risk_budget_hit_rate": 0.731707,
      "trade_count": 164,
      "execution_rows_used": 396,
      "stop_mode": "stop_ref(ema10)",
      "rpt": 0.0025,
      "rpt_label": "0.25%"
    },
    {
      "cumulative_return": 0.15599,
      "max_drawdown": 0.141817,
      "daily_sharpe": 0.883137,
      "annual_turnover": 2.372633,
      "avg_slot_utilization": 0.784887,
      "max_single_name_weight": 0.154808,
      "stop_ref_fallback": 0,
      "exposure_cap_clipped": 0,
      "exposure_fallback_day_ratio": 0.037783,
      "risk_budget_hit_rate": 0.731707,
      "trade_count": 164,
      "execution_rows_used": 396,
      "stop_mode": "stop_ref(ema10)",
      "rpt": 0.005,
      "rpt_label": "0.50%"
    },
    {
      "cumulative_return": 0.228749,
      "max_drawdown": 0.205989,
      "daily_sharpe": 0.872644,
      "annual_turnover": 3.606248,
      "avg_slot_utilization": 0.784887,
      "max_single_name_weight": 0.222695,
      "stop_ref_fallback": 0,
      "exposure_cap_clipped": 0,
      "exposure_fallback_day_ratio": 0.037783,
      "risk_budget_hit_rate": 0.731707,
      "trade_count": 164,
      "execution_rows_used": 396,
      "stop_mode": "stop_ref(ema10)",
      "rpt": 0.0075,
      "rpt_label": "0.75%"
    },
    {
      "cumulative_return": 0.220952,
      "max_drawdown": 0.287301,
      "daily_sharpe": 0.711587,
      "annual_turnover": 4.484821,
      "avg_slot_utilization": 0.784887,
      "max_single_name_weight": 0.282004,
      "stop_ref_fallback": 0,
      "exposure_cap_clipped": 2,
      "exposure_fallback_day_ratio": 0.037783,
      "risk_budget_hit_rate": 0.731707,
      "trade_count": 164,
      "execution_rows_used": 396,
      "stop_mode": "stop_ref(ema10)",
      "rpt": 0.01,
      "rpt_label": "1.00%"
    },
    {
      "cumulative_return": 0.156786,
      "max_drawdown": 0.425625,
      "daily_sharpe": 0.453767,
      "annual_turnover": 5.941523,
      "avg_slot_utilization": 0.78539,
      "max_single_name_weight": 0.321187,
      "stop_ref_fallback": 0,
      "exposure_cap_clipped": 4,
      "exposure_fallback_day_ratio": 0.037783,
      "risk_budget_hit_rate": 0.756098,
      "trade_count": 164,
      "execution_rows_used": 396,
      "stop_mode": "stop_ref(ema10)",
      "rpt": 0.015,
      "rpt_label": "1.50%"
    },
    {
      "cumulative_return": 0.053318,
      "max_drawdown": 0.121131,
      "daily_sharpe": 0.49831,
      "annual_turnover": 1.416272,
      "avg_slot_utilization": 0.784887,
      "max_single_name_weight": 0.058898,
      "stop_ref_fallback": 82,
      "exposure_cap_clipped": 0,
      "exposure_fallback_day_ratio": 0.037783,
      "risk_budget_hit_rate": 0.658537,
      "trade_count": 164,
      "execution_rows_used": 396,
      "stop_mode": "fallback(8%)",
      "rpt": 0.0025,
      "rpt_label": "0.25%"
    },
    {
      "cumulative_return": 0.099147,
      "max_drawdown": 0.230172,
      "daily_sharpe": 0.493418,
      "annual_turnover": 2.809911,
      "avg_slot_utilization": 0.784887,
      "max_single_name_weight": 0.111374,
      "stop_ref_fallback": 82,
      "exposure_cap_clipped": 0,
      "exposure_fallback_day_ratio": 0.037783,
      "risk_budget_hit_rate": 0.658537,
      "trade_count": 164,
      "execution_rows_used": 396,
      "stop_mode": "fallback(8%)",
      "rpt": 0.005,
      "rpt_label": "0.50%"
    },
    {
      "cumulative_return": 0.139075,
      "max_drawdown": 0.326639,
      "daily_sharpe": 0.494512,
      "annual_turnover": 4.157177,
      "avg_slot_utilization": 0.784887,
      "max_single_name_weight": 0.159763,
      "stop_ref_fallback": 82,
      "exposure_cap_clipped": 1,
      "exposure_fallback_day_ratio": 0.037783,
      "risk_budget_hit_rate": 0.658537,
      "trade_count": 164,
      "execution_rows_used": 396,
      "stop_mode": "fallback(8%)",
      "rpt": 0.0075,
      "rpt_label": "0.75%"
    },
    {
      "cumulative_return": 0.154847,
      "max_drawdown": 0.417741,
      "daily_sharpe": 0.46248,
      "annual_turnover": 5.435578,
      "avg_slot_utilization": 0.785894,
      "max_single_name_weight": 0.207605,
      "stop_ref_fallback": 82,
      "exposure_cap_clipped": 0,
      "exposure_fallback_day_ratio": 0.037783,
      "risk_budget_hit_rate": 0.658537,
      "trade_count": 164,
      "execution_rows_used": 396,
      "stop_mode": "fallback(8%)",
      "rpt": 0.01,
      "rpt_label": "1.00%"
    },
    {
      "cumulative_return": 0.094578,
      "max_drawdown": 0.589822,
      "daily_sharpe": 0.3307,
      "annual_turnover": 7.202366,
      "avg_slot_utilization": 0.785894,
      "max_single_name_weight": 0.300108,
      "stop_ref_fallback": 82,
      "exposure_cap_clipped": 4,
      "exposure_fallback_day_ratio": 0.037783,
      "risk_budget_hit_rate": 0.646341,
      "trade_count": 164,
      "execution_rows_used": 396,
      "stop_mode": "fallback(8%)",
      "rpt": 0.015,
      "rpt_label": "1.50%"
    }
  ],
  "equal_baseline": {
    "cumulative_return": -0.084886,
    "max_drawdown": 0.537004,
    "daily_sharpe": -0.010119,
    "annual_turnover": 5.813656,
    "avg_slot_utilization": 0.784887,
    "max_single_name_weight": 0.301768,
    "stop_ref_fallback": 0,
    "exposure_cap_clipped": 0,
    "exposure_fallback_day_ratio": 0.037783,
    "risk_budget_hit_rate": null,
    "trade_count": 164,
    "execution_rows_used": 396
  },
  "windows": [
    {
      "window": "W1_2024-09_2025-06",
      "row_count": 518,
      "equal": {
        "cumulative_return": -0.182901,
        "max_drawdown": 0.376796,
        "daily_sharpe": -0.500064,
        "annual_turnover": 6.874007,
        "avg_slot_utilization": 0.771287,
        "max_single_name_weight": 0.301768,
        "stop_ref_fallback": 0,
        "exposure_cap_clipped": 0,
        "exposure_fallback_day_ratio": 0.0,
        "risk_budget_hit_rate": null,
        "trade_count": 82,
        "execution_rows_used": 201
      },
      "risk_budget": {
        "cumulative_return": 0.036721,
        "max_drawdown": 0.09669,
        "daily_sharpe": 0.466477,
        "annual_turnover": 2.415281,
        "avg_slot_utilization": 0.771287,
        "max_single_name_weight": 0.133479,
        "stop_ref_fallback": 0,
        "exposure_cap_clipped": 0,
        "exposure_fallback_day_ratio": 0.0,
        "risk_budget_hit_rate": 0.658537,
        "trade_count": 82,
        "execution_rows_used": 201
      }
    },
    {
      "window": "W2_2025-07_2025-12",
      "row_count": 264,
      "equal": {
        "cumulative_return": -0.141593,
        "max_drawdown": 0.336676,
        "daily_sharpe": -0.961119,
        "annual_turnover": 7.312581,
        "avg_slot_utilization": 0.788148,
        "max_single_name_weight": 0.255584,
        "stop_ref_fallback": 0,
        "exposure_cap_clipped": 0,
        "exposure_fallback_day_ratio": 0.0,
        "risk_budget_hit_rate": null,
        "trade_count": 56,
        "execution_rows_used": 134
      },
      "risk_budget": {
        "cumulative_return": 0.067877,
        "max_drawdown": 0.090452,
        "daily_sharpe": 1.187609,
        "annual_turnover": 2.850065,
        "avg_slot_utilization": 0.788148,
        "max_single_name_weight": 0.16817,
        "stop_ref_fallback": 0,
        "exposure_cap_clipped": 0,
        "exposure_fallback_day_ratio": 0.0,
        "risk_budget_hit_rate": 0.678571,
        "trade_count": 56,
        "execution_rows_used": 134
      }
    },
    {
      "window": "W3_2026-03_2026-06",
      "row_count": 44,
      "equal": {
        "cumulative_return": 0.283558,
        "max_drawdown": 0.095297,
        "daily_sharpe": 3.19582,
        "annual_turnover": 5.400353,
        "avg_slot_utilization": 0.673418,
        "max_single_name_weight": 0.22165,
        "stop_ref_fallback": 0,
        "exposure_cap_clipped": 0,
        "exposure_fallback_day_ratio": 0.189873,
        "risk_budget_hit_rate": null,
        "trade_count": 28,
        "execution_rows_used": 78
      },
      "risk_budget": {
        "cumulative_return": 0.080866,
        "max_drawdown": 0.023625,
        "daily_sharpe": 3.584274,
        "annual_turnover": 2.025266,
        "avg_slot_utilization": 0.673418,
        "max_single_name_weight": 0.140267,
        "stop_ref_fallback": 0,
        "exposure_cap_clipped": 0,
        "exposure_fallback_day_ratio": 0.189873,
        "risk_budget_hit_rate": 1.0,
        "trade_count": 28,
        "execution_rows_used": 78
      }
    }
  ],
  "signal_kinds": [
    {
      "signal_kind": "uptrend_momentum",
      "row_count": 1170,
      "equal_cum": 0.234783,
      "equal_mdd": 0.087279,
      "rb_cum": 0.13304,
      "rb_mdd": 0.039802,
      "rb_sharpe": 2.724519,
      "stop_ref_fallback": 15
    },
    {
      "signal_kind": "fresh_trend_watchlist",
      "row_count": 1160,
      "equal_cum": 0.386812,
      "equal_mdd": 0.119138,
      "rb_cum": 0.209474,
      "rb_mdd": 0.064269,
      "rb_sharpe": 3.759456,
      "stop_ref_fallback": 15
    },
    {
      "signal_kind": "factor_screen",
      "row_count": 1011,
      "equal_cum": -0.086722,
      "equal_mdd": 0.128046,
      "rb_cum": -0.034515,
      "rb_mdd": 0.049294,
      "rb_sharpe": -2.476041,
      "stop_ref_fallback": 10
    },
    {
      "signal_kind": "stock_candidate",
      "row_count": 826,
      "equal_cum": -0.084886,
      "equal_mdd": 0.537004,
      "rb_cum": 0.15599,
      "rb_mdd": 0.141817,
      "rb_sharpe": 0.883137,
      "stop_ref_fallback": 0
    },
    {
      "signal_kind": "mean_reversion",
      "row_count": 610,
      "equal_cum": 0.00541,
      "equal_mdd": 0.186191,
      "rb_cum": 0.102839,
      "rb_mdd": 0.093388,
      "rb_sharpe": 0.603533,
      "stop_ref_fallback": 55
    },
    {
      "signal_kind": "theme_breakout",
      "row_count": 560,
      "equal_cum": 1.530113,
      "equal_mdd": 0.185275,
      "rb_cum": 0.574092,
      "rb_mdd": 0.078302,
      "rb_sharpe": 1.661358,
      "stop_ref_fallback": 79
    },
    {
      "signal_kind": "hybrid_fusion",
      "row_count": 223,
      "equal_cum": 0.098564,
      "equal_mdd": 0.101643,
      "rb_cum": 0.051331,
      "rb_mdd": 0.045365,
      "rb_sharpe": 1.476862,
      "stop_ref_fallback": 15
    }
  ],
  "coverage": {
    "total_rows": 826,
    "has_entry_price": 826,
    "has_ema10": 826,
    "valid_stop_ref": 826,
    "fallback_needed": 0,
    "valid_stop_ref_ratio": 1.0
  },
  "cliffs": [
    "回撤从 rpt=0.75%(20.60%) 到 rpt=1.00%(28.73%) 跳升 8.13%",
    "回撤从 rpt=1.00%(28.73%) 到 rpt=1.50%(42.56%) 跳升 13.83%",
    "收益从 rpt=1.00% 到 1.50% 下降 6.42%"
  ]
}
```
