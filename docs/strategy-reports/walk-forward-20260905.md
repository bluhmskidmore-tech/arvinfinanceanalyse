# Walk-Forward 样本外验证框架 — 首轮体检报告

> 生成时间：2026-09-05 09:53:20+0800 | 引擎 `pbt_v2_path_mode` | 模式 `path` | 变体 `fixed_20d`
> DuckDB `data\moss.duckdb`（只读） | 执行历史 5833 行，其中可用 5610 行 | 回测调用 566 次
> 主切割：训练 6 月 / 验证 2 月 / 步长 2 月，选参目标 `sharpe`，训练期 purge=True
> 口径：path 模式盯市 fixed_20d；T+1 开盘执行历史；20d 净收益按引擎 coalesce 链 (return_20d_net_adj -> return_20d_net) 取值；逐日 gate 敞口优先、缺失退回状态 fallback；敞口 T 日决策 T+1 生效；成本/滑点取 POLICY

**历史运行记录（2026-09-05 验收补注）**：以下数值保留原 `pbt_v2_path_mode` 运行结果及同名 JSON，未重算业绩。当前引擎已升级为 `pbt_v3_open_equity_effective_exposure`；本报告不证明 v3 下的样本外结论，当前版本复验为 `PENDING`。复现历史数字需要同版引擎、输入数据与配置。

本次只校正文稿与原始 JSON 的一致性，不查询数据库或修改策略。原文引用的首版 5560 行和可用 4311 行没有随本次 JSON 提供对应运行证据，不能据此解释历史增减；5833 与 5560 的算术差为 273，不能写成去重减少 14 行。

---

## 0. 执行摘要

### 0.1 七策略样本外判定（等权 fixed_20d，主切割）

| signal_kind | 可用行 | 历史区间 | OOS窗数 | OOS链式收益 | OOS链式超额(vs gate) | 正超额窗 | 全窗口IS收益 | 衰减率(累计) | 判定 |
|---|---:|---|---:|---:|---:|---|---:|---:|---|
| stock_candidate | 770 | 2024-09-24~2026-06-15 | 5 | -28.53% | -54.30% | 1/5 | -3.54% | IS≤0(Δ-24.99%) | 样本外削弱 |
| theme_breakout | 559 | 2024-08-30~2026-07-10 | 5 | 180.06% | 154.13% | 5/5 | 118.61% | 1.52x | 样本外支持 |
| mean_reversion | 602 | 2024-09-24~2026-07-08 | 4 | -4.29% | -11.62% | 1/4 | 2.66% | -1.62x | 样本外削弱 |
| uptrend_momentum | 1200 | 2026-03-25~2026-07-08 | 0 | NA | NA | NA | 7.38% | NA | 不可判(窗数不足) |
| fresh_trend_watchlist | 1180 | 2026-03-25~2026-07-08 | 0 | NA | NA | NA | 14.98% | NA | 不可判(窗数不足) |
| factor_screen | 1071 | 2026-04-30~2026-07-10 | 0 | NA | NA | NA | -7.69% | NA | 不可判(窗数不足) |
| hybrid_fusion | 228 | 2026-03-18~2026-07-10 | 0 | NA | NA | NA | 0.09% | NA | 不可判(窗数不足) |

### 0.2 risk_budget 参数稳健性（主切割）

| signal_kind | OOS活动窗 | 选参轨迹(逐窗) | 漂移率 | OOS(逐窗选参) | OOS(固定rpt=0.5%) | OOS(事后最优) | IS(rpt=0.5%) | 选参增益 |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| stock_candidate | 5 | 0.75% → 0.25% → 0.25% → 0.25% → 1.00% | 0.5000 | -0.03% | -2.48% | -8.75% | 16.00% | 2.45% |
| theme_breakout | 5 | 1.00% → 1.00% → 1.00% → 0.75% → 0.25% | 0.5000 | 89.57% | 54.57% | 119.70% | 44.30% | 34.99% |
| mean_reversion | 4 | 0.75% → 0.75% → 1.00% → 1.00% → 0.75% | 0.5000 | 4.87% | 1.16% | 4.28% | 10.24% | 3.72% |
| uptrend_momentum | 0 | NA → NA → NA → NA → NA | NA | NA | NA | NA | 4.07% | NA |
| fresh_trend_watchlist | 0 | NA → NA → NA → NA → NA | NA | NA | NA | NA | 8.03% | NA |
| factor_screen | 0 | NA → NA → NA → NA → NA | NA | NA | NA | NA | -2.84% | NA |
| hybrid_fusion | 0 | NA → NA → NA → NA → NA | NA | NA | NA | NA | -1.94% | NA |

### 0.3 结论要点

- **可判定的只有 3/7 个策略**：stock_candidate、theme_breakout、mean_reversion 有足够验证窗；uptrend_momentum、fresh_trend_watchlist、factor_screen、hybrid_fusion 因历史全部落在 2026-03 之后（两代边界之后的段不足以生成 6+2 个月的窗口）而**未被检验**——它们的全窗口结论既没被支持也没被推翻。
- **theme_breakout：样本外支持**。5/5 个验证窗正超额，链式超额 154.13%，链式收益 180.06%（全窗口 IS 118.61%）。优势在滚动切割下没有消失。
- **stock_candidate：样本外削弱**。仅 1/5 个验证窗正超额，链式超额 -54.30%；逐窗最差 -13.17%，最大窗内回撤 17.45%。
- **mean_reversion：样本外削弱**。仅 1/4 个验证窗正超额，链式超额 -11.62%；逐窗最差 -4.38%，最大窗内回撤 9.67%。
- **risk_budget rpt=0.5% 的样本内优势普遍缩水**：stock_candidate（IS 16.00% → OOS -2.48%）；theme_breakout（IS 44.30% → OOS 54.57%）；mean_reversion（IS 10.24% → OOS 1.16%）。全部为同一引擎、同一口径下的对照，差异来自切割方式而非参数实现。
- **最优 rpt 随窗漂移严重**：可判定策略的相邻窗切换率为 0.5000、0.5000、0.5000，各自众数分别是 stock_candidate=0.25%、theme_breakout=1.00%、mean_reversion=0.75%——**没有任何一个策略把 0.5% 选为众数**；训练窗选出的参数在验证窗的表现与事后最优参数也不重合（§4.1）。这说明 rpt 更像一个需要按 kind/区制分别校准的量，而不是一个全局稳健常数。
- **逐窗选参 vs 固定 0.5%**：3/3 个可判定策略上逐窗选参的链式 OOS 收益高于固定 0.5%（§0.2 选参增益列）；但窗数太少，该增益不足以支撑「上线自适应选参」的结论，只说明固定 0.5% 不是这几段里的最优点。

### 0.4 本次运行的去重证据与比较边界

- **本次去重计数**：加载 5847 行，去重后 5833 行，移除 14 行；join 扇出 14 行，表内重复 0 行。当前可用 5610 行；逐 kind 去重数为 {'hybrid_fusion': 5, 'mean_reversion': 4, 'stock_candidate': 5}，可用行以 §0.1 的本次结果为准。
- **重复键证据**：14 个重复键中，`ema10_conflict_keys=0`。该计数本身不证明去重前后业绩相同。
- **跨运行比较为 PENDING**：本次 payload 不含首版运行的输入和结果，不能据此判断历史行数变化、收益/回撤/超额/判定是否变化，或窗口夹取与训练期截断对选参的影响。

---

## 1. 数据缺口如实计数

全部分类来自可核对的列状态（不做因果推断）：

| signal_kind | 总行 | 不可执行 | 无20d退出日(截尾) | 有退出日无任何收益(遮挡) | 复权缺失走coalesce | 可用行 | 最后可用信号日 |
|---|---:|---:|---:|---:|---:|---:|---|
| stock_candidate | 812 | 41 | 42 | 0 | 0 | 770 | 2026-06-15 |
| theme_breakout | 575 | 16 | 16 | 0 | 0 | 559 | 2026-07-10 |
| mean_reversion | 655 | 33 | 53 | 0 | 0 | 602 | 2026-07-08 |
| uptrend_momentum | 1311 | 60 | 111 | 0 | 0 | 1200 | 2026-07-08 |
| fresh_trend_watchlist | 1216 | 22 | 36 | 0 | 0 | 1180 | 2026-07-08 |
| factor_screen | 1191 | 60 | 120 | 0 | 0 | 1071 | 2026-07-10 |
| hybrid_fusion | 268 | 20 | 40 | 0 | 0 | 228 | 2026-07-10 |

**四类已知缺口的处置**：

1. **执行历史月度空洞**：常被引用的 2026-01/2026-02 缺口在本次数据中确认缺失：2026-01、2026-02；框架不跨空洞生成窗口——空洞被 `max_gap_days` 与强制切割点共同拦成段边界。
2. **20d outcome 未成熟尾部（截尾）**：418 行无 `exit_date_20d`（信号日 2024-09-27~2026-08-24），一律排除在可用行之外，不进入任何窗口；这意味着最后一段验证窗天然被截断。
3. **有退出日但无任何 20d 收益（遮挡）**：0 行。本框架的输入表 `livermore_candidate_execution_history` **未出现**该症状（`stored_target_conflict` 是 `livermore_candidate_outcome_maturity` 在 `livermore_candidate_history` 上的运行期 issue，不落成执行历史的列状态）；如实计为 0，不臆造遮挡量。
4. **复权缺失行**：0 行有 `return_20d_net` 但无 `return_20d_net_adj`（信号日 ~），沿用引擎 coalesce 链 `return_20d_net_adj -> return_20d_net` 计入回测，逐 kind 计数见上表。本次未观测到复权缺失，不据此推断覆盖缺口。
   - 根因取证（分两类）：**(a) 日期级空洞** —— 0 行的 20d 目标日（共 0 个日期，散布于 ~）在 `stock_adjustment_factor` 中完全没有因子行；**(b) 逐票缺失** —— 复权缺失行中，其余行的目标日有因子但该股票缺行。
   - 其中尾部 0 行的目标日晚于因子表的稠密覆盖末日 2026-08-24（表内最大因子日 2026-08-24），信号日范围为 ~、目标日最远 。这些计数只描述本次输入覆盖，不能据此推断补载原因或特定历史缺口。

- 两代数据边界 `2026-01-05` 为强制切割点，任何窗口不得跨越。
- path 模式缺价格路径行：0（按成本计价降级）。

**加载器行数守恒（ema10 join 扇出 + 表内重复行）**：
- 共享加载器 `_load_execution_rows` 为取 `ema10` 左连 `livermore_candidate_history`，该表对同一 (stock_code, snapshot_as_of_date, signal_kind) 可能有 2 行，于是加载 5847 行 vs 表内（`entry_date` 非空）5833 行，**join 扇出 +14 行**（最大重复 2 次）。
- 执行历史表**自身**还有 0 行完全重复的执行行（同 `(signal_date, stock_code, signal_kind)`、同 run_id / formula_version / entry_date / 20d 收益）；加载后的最大重复倍数为 2。
- 该加载器是已提交的共享文件、扇出属继承问题，**本框架不改加载器**，而是在编排侧按 `signal_date, stock_code, signal_kind` 去重（ema10 非空优先，其次 ema10 最小，其次加载顺序首行）：5847 → 5833 行（−14，涉及 14 个键）；去重后行数与表内去重键数 5833 一致，即「一个 (信号日, 股票, 信号族) 一行」。逐 kind 去重行数：{'hybrid_fusion': 5, 'mean_reversion': 4, 'stock_candidate': 5}。
- 与上表口径的剩余差异只有两项且可核对：上表 SQL 不过滤 `entry_date`（195 行无 `entry_date`，无法建仓）、且把上述表内重复行各计一次；§0.1「可用行」是编排侧去重后的口径。
- 取舍说明：本次 14 个重复键的 `ema10_conflict_keys=0`；保留规则为 ema10 非空优先，其次 ema10 最小，其次加载顺序首行。是否影响交易路径与业绩需要去重前后同输入回放，不能由重复键计数直接判定。

---

## 2. 切割方案与窗口清单

### 2.1 分段（强制切割点 / 数据空洞）

| segment | 起 | 止 | 信号日数 | 起始原因 |
|---|---|---|---:|---|
| S1 | 2024-08-30 | 2025-12-31 | 249 | series_start |
| S2 | 2026-03-18 | 2026-07-10 | 65 | forced_cut:2026-01-05+data_gap:77d |

### 2.2 窗口

| window | segment | 训练区间 | 验证区间 | 验证末日被段边界夹短 |
|---|---|---|---|---|
| S1W1 | S1 | 2024-08-01~2025-01-31 | 2025-02-01~2025-03-31 | 否 |
| S1W2 | S1 | 2024-10-01~2025-03-31 | 2025-04-01~2025-05-31 | 否 |
| S1W3 | S1 | 2024-12-01~2025-05-31 | 2025-06-01~2025-07-31 | 否 |
| S1W4 | S1 | 2025-02-01~2025-07-31 | 2025-08-01~2025-09-30 | 否 |
| S1W5 | S1 | 2025-04-01~2025-09-30 | 2025-10-01~2025-11-30 | 否 |

- 验证窗互不重叠：True（链式复利成立的前提）
- 跨越强制切割点的窗口：无（窗口生成阶段已把验证末日夹在段实际边界内；若仍出现跨界，`analyze_schedule` 直接抛 `WalkForwardLeakageError` 拒绝出报告）
- 验证末日被段边界夹短的窗口：无（夹短窗的验证时长小于名义 valid_months，其年化数字更不稳定）

---

## 3. 无参数型验证：七个 signal_kind 等权 fixed_20d

### 3.1 逐窗样本外表现

| signal_kind | window | 验证区间 | 验证行 | 买入笔 | 收益 | 回撤 | Sharpe | gate基准 | 超额 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| stock_candidate | S1W1 | 2025-02-01~2025-03-31 | 143 | 10 | -0.94% | 17.45% | 0.0604 | -2.68% | 1.75% |
| stock_candidate | S1W2 | 2025-04-01~2025-05-31 | 60 | 6 | -3.70% | 4.63% | -2.8872 | 3.17% | -6.87% |
| stock_candidate | S1W3 | 2025-06-01~2025-07-31 | 93 | 12 | -13.17% | 13.72% | -2.0474 | 13.09% | -26.25% |
| stock_candidate | S1W4 | 2025-08-01~2025-09-30 | 128 | 12 | -3.24% | 9.50% | -0.1700 | 12.26% | -15.50% |
| stock_candidate | S1W5 | 2025-10-01~2025-11-30 | 77 | 10 | -10.83% | 14.25% | -2.0296 | -1.32% | -9.50% |
| theme_breakout | S1W1 | 2025-02-01~2025-03-31 | 54 | 8 | 11.73% | 8.81% | 1.4323 | -1.97% | 13.70% |
| theme_breakout | S1W2 | 2025-04-01~2025-05-31 | 43 | 8 | 9.69% | 5.55% | 1.8316 | 2.72% | 6.97% |
| theme_breakout | S1W3 | 2025-06-01~2025-07-31 | 9 | 9 | 21.35% | 7.47% | 3.1675 | 12.10% | 9.24% |
| theme_breakout | S1W4 | 2025-08-01~2025-09-30 | 101 | 13 | 61.24% | 10.38% | 4.2167 | 11.58% | 49.65% |
| theme_breakout | S1W5 | 2025-10-01~2025-11-30 | 62 | 10 | 16.79% | 11.19% | 1.8635 | -0.03% | 16.82% |
| mean_reversion | S1W1 | 2025-02-01~2025-03-31 | 116 | 10 | 1.39% | 7.32% | -0.1592 | -1.97% | 3.36% |
| mean_reversion | S1W2 | 2025-04-01~2025-05-31 | 128 | 10 | -4.36% | 9.16% | -1.8144 | 3.17% | -7.53% |
| mean_reversion | S1W3 | 2025-06-01~2025-07-31 | 71 | 5 | 3.22% | 8.86% | 0.5210 | 6.45% | -3.24% |
| mean_reversion | S1W5 | 2025-10-01~2025-11-30 | 14 | 9 | -4.38% | 9.67% | -0.8895 | -0.31% | -4.06% |
| uptrend_momentum | — | — | 0 | 0 | NA | NA | NA | NA | NA |
| fresh_trend_watchlist | — | — | 0 | 0 | NA | NA | NA | NA | NA |
| factor_screen | — | — | 0 | 0 | NA | NA | NA | NA | NA |
| hybrid_fusion | — | — | 0 | 0 | NA | NA | NA | NA | NA |

### 3.2 聚合：衰减率 / 稳定性 / 判定

OOS窗只计**有实际买入**的验证窗（该 kind 在某窗无信号时不计入，也不参与链式复利）。
注意 OOS 覆盖期与 IS 覆盖期不同（见下表 OOS区间 列），因此**期间中性的比较应看链式超额**（策略 − 同期 gate 择时基准），而不是链式收益与 IS 收益的直接相除。

| signal_kind | OOS窗 | OOS区间 | 链式OOS | 链式超额 | 年化OOS | 最差窗 | 最大窗内回撤 | IS累计 | IS年化 | 衰减(累计) | 衰减(年化) | 收益正窗 | 超额正窗 | 判定 | 理由 |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|
| stock_candidate | 5 | 2025-02-01~2025-11-30 | -28.53% | -54.30% | -33.27% | -13.17% | 17.45% | -3.54% | -1.98% | IS≤0(Δ-24.99%) | IS≤0(Δ-31.30%) | 0/5 | 1/5 | 样本外削弱 | 1/5 窗正超额，链式超额 -54.30% |
| theme_breakout | 5 | 2025-02-01~2025-11-30 | 180.06% | 154.13% | 245.75% | 9.69% | 11.19% | 118.61% | 50.01% | 1.52x | 4.91x | 5/5 | 5/5 | 样本外支持 | 5/5 窗正超额且链式超额 +154.13% |
| mean_reversion | 4 | 2025-02-01~2025-11-30 | -4.29% | -11.62% | -6.41% | -4.38% | 9.67% | 2.66% | 1.42% | -1.62x | -4.51x | 2/4 | 1/4 | 样本外削弱 | 1/4 窗正超额，链式超额 -11.62% |
| uptrend_momentum | 0 | — | NA | NA | NA | NA | NA | 7.38% | 21.76% | NA | NA | NA | NA | 不可判(窗数不足) | 验证窗仅 0 个 (< 3)，自由度不足，不下结论 |
| fresh_trend_watchlist | 0 | — | NA | NA | NA | NA | NA | 14.98% | 47.11% | NA | NA | NA | NA | 不可判(窗数不足) | 验证窗仅 0 个 (< 3)，自由度不足，不下结论 |
| factor_screen | 0 | — | NA | NA | NA | NA | NA | -7.69% | -26.94% | NA | NA | NA | NA | 不可判(窗数不足) | 验证窗仅 0 个 (< 3)，自由度不足，不下结论 |
| hybrid_fusion | 0 | — | NA | NA | NA | NA | NA | 0.09% | 0.24% | NA | NA | NA | NA | 不可判(窗数不足) | 验证窗仅 0 个 (< 3)，自由度不足，不下结论 |

---

## 4. 参数型验证：risk_budget rpt 网格

训练窗按 `sharpe` 选参，验证窗只用该参数。训练切片额外做 purge：只保留 20d 退出日 ≤ 训练末日的行，保证选参时刻这些收益已完全兑现。

### 4.1 逐窗选参与样本外结果

「训练行」列格式为 purge 后(purge 前)；训练行少于 20 条的窗不选参（记 NA），避免在几乎没有观测的训练窗上假装完成了参数优化。「事后最优」是用验证窗自身结果反选出的参数，仅用于度量选参损失，**不是可实施的策略**。

| signal_kind | window | 训练行(purge前) | 训练分数 0.25/0.50/0.75/1.00% | 选中 | 验证行 | OOS收益(选中) | OOS收益(0.5%) | 事后最优 | OOS收益(事后最优) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| stock_candidate | S1W1 | 233(237) | 0.1355 / 0.1454 / 0.1537 / -0.1255 | 0.75% | 143 | 11.30% | 7.60% | 0.25% | 3.83% |
| stock_candidate | S1W2 | 291(364) | 1.8201 / 1.8129 / 1.8054 / 1.4192 | 0.25% | 60 | -1.34% | -2.68% | 0.25% | -1.34% |
| stock_candidate | S1W3 | 241(295) | 2.0873 / 2.0790 / 2.0704 / 1.7392 | 0.25% | 93 | -1.27% | -2.54% | 0.50% | -2.54% |
| stock_candidate | S1W4 | 254(296) | 0.7694 / 0.7493 / 0.7295 / 0.2371 | 0.25% | 128 | -0.40% | -0.82% | 1.00% | -1.28% |
| stock_candidate | S1W5 | 222(281) | -1.3924 / -1.3778 / -1.3629 / -1.3196 | 1.00% | 77 | -7.40% | -3.65% | 1.00% | -7.40% |
| theme_breakout | S1W1 | 134(161) | 2.3747 / 2.3881 / 2.4009 / 2.4729 | 1.00% | 54 | 12.71% | 7.85% | 0.75% | 11.72% |
| theme_breakout | S1W2 | 178(189) | 1.0673 / 1.1017 / 1.1352 / 1.1922 | 1.00% | 43 | 10.38% | 6.22% | 1.00% | 10.38% |
| theme_breakout | S1W3 | 136(150) | 0.5195 / 0.5460 / 0.5724 / 0.6322 | 1.00% | 9 | 13.80% | 7.09% | 1.00% | 13.80% |
| theme_breakout | S1W4 | 101(106) | 0.4465 / 0.4470 / 0.4934 / 0.2014 | 0.75% | 101 | 30.55% | 19.83% | 1.00% | 41.83% |
| theme_breakout | S1W5 | 103(153) | 1.7471 / 1.7462 / 1.7444 / 1.7270 | 0.25% | 62 | 2.56% | 5.15% | 1.00% | 10.38% |
| mean_reversion | S1W1 | 31(34) | 1.7651 / 1.7856 / 1.8035 / 1.5891 | 0.75% | 116 | 3.35% | 2.26% | 1.00% | 3.86% |
| mean_reversion | S1W2 | 112(130) | 0.8242 / 0.8435 / 0.8986 / 0.7347 | 0.75% | 128 | -0.44% | -1.55% | 0.75% | -0.44% |
| mean_reversion | S1W3 | 159(252) | -0.1992 / -0.2027 / -0.2008 / -0.0584 | 1.00% | 71 | 5.13% | 2.56% | 1.00% | 5.13% |
| mean_reversion | S1W4 | 315(315) | -0.5285 / -0.5186 / -0.5088 / 0.3295 | 1.00% | 0 | NA | NA | NA | NA |
| mean_reversion | S1W5 | 199(199) | -1.2978 / 0.3677 / 1.2659 / 1.0102 | 0.75% | 14 | -3.05% | -2.04% | 1.00% | -4.07% |
| uptrend_momentum | — | — | — | NA | 0 | NA | NA | NA | NA |
| fresh_trend_watchlist | — | — | — | NA | 0 | NA | NA | NA | NA |
| factor_screen | — | — | — | NA | 0 | NA | NA | NA | NA |
| hybrid_fusion | — | — | — | NA | 0 | NA | NA | NA | NA |

### 4.2 参数漂移度

| signal_kind | 有效选参窗 | 取值个数 | 众数 | 众数占比 | 切换次数 | 切换率 | 平均步长(rpt) |
|---|---:|---:|---:|---:|---:|---:|---:|
| stock_candidate | 5 | 3 | 0.25% | 0.6000 | 2.0000 | 0.5000 | 0.0031 |
| theme_breakout | 5 | 3 | 1.00% | 0.6000 | 2.0000 | 0.5000 | 0.0019 |
| mean_reversion | 5 | 2 | 0.75% | 0.6000 | 2.0000 | 0.5000 | 0.0013 |
| uptrend_momentum | 0 | 0 | NA | NA | NA | NA | NA |
| fresh_trend_watchlist | 0 | 0 | NA | NA | NA | NA | NA |
| factor_screen | 0 | 0 | NA | NA | NA | NA | NA |
| hybrid_fusion | 0 | 0 | NA | NA | NA | NA | NA |

### 4.3 样本外 vs 全窗口 in-sample（rpt=0.5%）

| signal_kind | IS累计(0.5%) | IS回撤(0.5%) | IS最优rpt | OOS链式(0.5%) | OOS链式(逐窗选参) | 衰减率(0.5%) | 超额正窗(0.5%) | 判定(0.5%) |
|---|---:|---:|---:|---:|---:|---:|---|---|
| stock_candidate | 16.00% | 14.01% | 0.25% | -2.48% | -0.03% | -0.16x | 1/5 | 样本外削弱 |
| theme_breakout | 44.30% | 14.97% | 0.75% | 54.57% | 89.57% | 1.23x | 4/5 | 样本外支持 |
| mean_reversion | 10.24% | 9.31% | 1.00% | 1.16% | 4.87% | 0.11x | 1/4 | 样本外削弱 |
| uptrend_momentum | 4.07% | 14.97% | 1.00% | NA | NA | NA | NA | 不可判(窗数不足) |
| fresh_trend_watchlist | 8.03% | 16.57% | 1.00% | NA | NA | NA | NA | 不可判(窗数不足) |
| factor_screen | -2.84% | 4.86% | 1.00% | NA | NA | NA | NA | 不可判(窗数不足) |
| hybrid_fusion | -1.94% | 13.59% | 0.25% | NA | NA | NA | NA | 不可判(窗数不足) |

---

## 5. 与全窗口结论的对照

对照口径：本表的「全窗口 IS」由本次运行同一引擎重算，与既有报告口径一致但数据已滚动更新，
因此绝对数可能与历史报告略有差异；结论方向的对照以本次内部一致的数字为准。

| 策略 | 全窗口 IS 结论（本次重算） | 样本外结论 | 对照 |
|---|---|---|---|
| stock_candidate | 累计 -3.54%，超额 -30.51% | 样本外削弱；链式超额 -54.30% | 样本外一致为负（IS 负结论被确认） |
| theme_breakout | 累计 118.61%，超额 93.70% | 样本外支持；链式超额 154.13% | **被样本外支持** |
| mean_reversion | 累计 2.66%，超额 -19.89% | 样本外削弱；链式超额 -11.62% | 样本外一致为负（IS 负结论被确认） |
| uptrend_momentum | 累计 7.38%，超额 8.59% | 不可判(窗数不足)；链式超额 NA | **不可判**（窗数不足） |
| fresh_trend_watchlist | 累计 14.98%，超额 16.19% | 不可判(窗数不足)；链式超额 NA | **不可判**（窗数不足） |
| factor_screen | 累计 -7.69%，超额 -2.70% | 不可判(窗数不足)；链式超额 NA | **不可判**（窗数不足） |
| hybrid_fusion | 累计 0.09%，超额 1.48% | 不可判(窗数不足)；链式超额 NA | **不可判**（窗数不足） |

---

## 6. 敏感性切割：compact_1t_1v_1s（探索性，不作为判定依据）

训练 1 月 / 验证 1 月 / 步长 1 月。目的有二：(1) 检验主切割结论对窗口粒度的敏感性；(2) 给只有 2026-03 之后历史的短史策略一个能落窗的粒度。该粒度下单窗样本极小、训练期几乎无自由度，**结论一律不升级为判定**。

该切割覆盖的 OOS 区间与主切割**不同且更长**（见 OOS区间 列），因此其数值水平不能与 §3 直接比较；可比的只有方向（超额正窗比例、链式超额符号）。

另一处近似：本切割在 2 个数据段上都生成了窗口，链式复利把段与段之间的数据空洞当作连续持有处理（窗口本身仍不跨段）。

| signal_kind | OOS窗 | OOS区间 | 链式OOS | 链式超额 | 收益正窗 | 超额正窗 | IS累计 | 衰减(累计) | 参考判定 |
|---|---:|---|---:|---:|---|---|---:|---:|---|
| stock_candidate | 18 | 2024-09-01~2026-06-30 | 47.73% | 2.28% | 9/18 | 8/18 | -3.54% | IS≤0(Δ51.26%) | 方向不稳定 |
| theme_breakout | 20 | 2024-09-01~2026-07-31 | 220.80% | 194.47% | 13/20 | 14/20 | 118.61% | 1.86x | 样本外支持 |
| mean_reversion | 16 | 2024-09-01~2026-07-31 | -12.33% | -39.17% | 7/16 | 5/16 | 2.66% | -4.64x | 样本外削弱 |
| uptrend_momentum | 4 | 2026-04-01~2026-07-31 | -18.92% | -15.85% | 2/4 | 2/4 | 7.38% | -2.56x | 样本外削弱 |
| fresh_trend_watchlist | 4 | 2026-04-01~2026-07-31 | 41.79% | 48.02% | 3/4 | 3/4 | 14.98% | 2.79x | 样本外支持 |
| factor_screen | 4 | 2026-04-01~2026-07-31 | -9.53% | 0.04% | 1/4 | 1/4 | -7.69% | IS≤0(Δ-1.85%) | 样本外削弱 |
| hybrid_fusion | 4 | 2026-04-01~2026-07-31 | -4.64% | -3.01% | 3/4 | 3/4 | 0.09% | -50.21x | 样本外削弱 |

risk_budget 逐窗选参轨迹（同一粒度）：

注意：1 个月的训练窗在 purge（要求 20d 结果已兑现）之后往往不足 20 行，因此多数 kind 的「有效选参窗」为 0。**这本身是结论**：在月度粒度上无法在不偷看未来的前提下完成参数选择；「OOS(固定0.5%)」列不依赖选参，仍然可读。

| signal_kind | 有效选参窗 | 众数 | 切换率 | OOS(选参) | OOS(固定0.5%) |
|---|---:|---:|---:|---:|---:|
| stock_candidate | 0 | NA | NA | NA | 47.37% |
| theme_breakout | 0 | NA | NA | NA | 91.22% |
| mean_reversion | 0 | NA | NA | NA | 2.10% |
| uptrend_momentum | 1 | 1.00% | NA | -12.28% | 1.50% |
| fresh_trend_watchlist | 2 | 0.25% | 1.0000 | -18.92% | 16.53% |
| factor_screen | 1 | 1.00% | NA | 1.12% | -3.72% |
| hybrid_fusion | 0 | NA | NA | NA | 8.71% |

---

## 7. 方法学附录

### 7.1 切割图示

```
S1 [2024-08-30..2025-12-31] (series_start)
    months: 2408 2409 2410 2411 2412 2501 2502 2503 2504 2505 2506 2507 2508 2509 2510 2511 2512
      S1W1: T    T    T    T    T    T    V    V    .    .    .    .    .    .    .    .    .
      S1W2: .    .    T    T    T    T    T    T    V    V    .    .    .    .    .    .    .
      S1W3: .    .    .    .    T    T    T    T    T    T    V    V    .    .    .    .    .
      S1W4: .    .    .    .    .    .    T    T    T    T    T    T    V    V    .    .    .
      S1W5: .    .    .    .    .    .    .    .    T    T    T    T    T    T    V    V    .

S2 [2026-03-18..2026-07-10] (forced_cut:2026-01-05+data_gap:77d)
    months: 2603 2604 2605 2606 2607
    (none): 该段跨度不足，本切割下未生成任何窗口

```

（T=训练月，V=验证月，.=同段内未被该窗覆盖的月）

### 7.2 防泄漏机制

| 机制 | 实现 | 断言位置 |
|---|---|---|
| 验证窗只见窗内信号 | `select_validation_rows` 按 `signal_date` 闭区间切片 | `tests/test_walk_forward_validation.py::test_validation_slice_only_contains_window_signal_dates` |
| 选参只用训练窗 | `select_training_rows` 按 `signal_date` 切片 | 同上文件 `test_training_slice_*` |
| 训练期 purge（20d 未兑现行剔除） | 训练行要求 `exit_date_20d <= train_end`，即选参时刻(`valid_start`)其收益已实现 | `test_training_rows_are_purged_of_unrealized_outcomes` |
| 未来数据不影响选参（纯逻辑） | 删除/篡改 `train_end` 之后的全部行，选参结果必须不变 | `test_parameter_selection_is_immune_to_future_rows` |
| 未来数据不影响选参（真实引擎） | 在真实引擎上篡改 `train_end` 之后的执行行与窗外路径价格，选参与训练分数必须逐字节不变 | `test_real_engine_parameter_selection_is_immune_to_future_rows` |
| 窗口不跨代际边界 | 分段在强制切割点与数据空洞处断开；验证末日再夹在段实际边界内，跨界则 `analyze_schedule` fail-fast | `test_windows_never_cross_forced_cut_date`、`test_segment_end_in_same_month_as_cut_does_not_leak_next_segment`、`test_analyze_schedule_fails_fast_on_crossing_window` |
| 价格路径按切片限定 | 只把本切片持仓的路径喂给引擎，避免其它窗口的路径污染交易日网格 | `test_scoped_price_paths_exclude_other_slices` |
| 训练路径按决策时点截断 | path 模式下停牌/跌停顺延会让训练时间轴越过 `train_end`；训练调用把每条路径的 bar 截到 `trade_date <= train_end` | `test_training_price_paths_are_truncated_at_train_end` |

注意：验证窗内建仓的持仓，其 20d 结果自然落在验证窗之后——这是「决策后的实现结果」，
不是前视；本框架禁止的是「决策时使用决策日之后的信息」。

### 7.3 指标定义

- **链式 OOS 收益** = ∏(1 + 各验证窗收益) − 1（验证窗互不重叠时成立，见 §2.2）；
  - **窗间持有期重叠（口径披露）**：窗口的互不重叠是按 `signal_date` 定义的，而验证窗末尾建仓的持仓其 20d 持有期会延伸到下一验证窗的日历区间内。本框架把每个验证窗当作独立重启的资金曲线（各窗从 `initial_capital` 起算、窗末清仓收口）再把窗收益相乘，因此链式收益是「连续换仓的近似」而非单条不间断资金曲线：跨窗的仓位延续、现金占用与相邻窗之间的相关性都没有被建模，相邻窗收益并非严格独立，链式数值的置信度低于单窗数值；
- **链式超额** = 链式策略收益 − 链式 gate 择时基准收益（`gate_timing_csi300`，与引擎同口径）；
- **衰减率(累计)** = 链式 OOS 收益 ÷ 全窗口 IS 累计收益；IS ≤ 0 时比值无意义，只给差值并标注；
- **衰减率(年化)** = OOS 年化 ÷ IS 年化，年化统一按 365/日历跨度（与引擎 `_annualization_factor` 同口径）；
- **超额符号一致率** = 正超额验证窗数 ÷ 可观测验证窗数；
- **参数漂移度** = 相邻窗选参发生变化的比例（切换率）+ 平均绝对步长；
- **判定阈值**：窗数 < 3 判「不可判」；否则超额正窗比 ≥ 2/3 且链式超额 > 0 判「样本外支持」，正窗比 ≤ 1/3 或链式超额 < 0 判「样本外削弱」，其余「方向不稳定」。

### 7.4 自由度与局限（如实披露）

1. **窗数本身很少**：主切割只产出 5 个验证窗，且全部落在同一个数据段内；任一策略的判定至多基于个位数的独立观测，统计力弱，只能作方向证据。
2. **短历史策略不可判**：uptrend_momentum、fresh_trend_watchlist、factor_screen、hybrid_fusion 在主切割下有效验证窗少于 3 个，本报告不对其给出样本外结论。其全窗口结论既未被支持也未被削弱——是**未被检验**。
3. **验证窗内持有期重叠**：20d 持有期使同一验证窗内的观测高度相关，有效独立观测数远小于行数；逐窗 Sharpe/回撤应视为噪声较大的读数。
4. **验证窗间持有期重叠**：窗口按 `signal_date` 互斥，但窗末建仓的 20d 持有期跨入下一窗日历区间；本框架每窗独立重启资金曲线后再链式相乘（§7.3），未建模跨窗仓位延续与现金占用，相邻窗收益不严格独立，链式收益应作方向性读数、不可当作可实盘复现的净值。
5. **尾部截断**：最后一段验证窗因 20d outcome 未回补而系统性缺少晚期信号，该窗结论对「窗末行情」不敏感，存在选择性幸存。
6. **市场状态标签可漂移**：逐日 gate 敞口与 market_state 来自重放，既有审计（factor_screen 门控复审）已记录标签漂移；所有状态条件化的窗口结果继承该不确定性。
7. **基准口径**：超额以 `gate_timing_csi300`（同敞口择时的 CSI300）为准，不是无风险利率或行业中性基准；策略与基准的敞口路径不同会带入 beta 残差。
8. **只验证了两类对象**：sizing 参数（rpt）与信号族本身；选股打分内部参数（如 momentum v2 的权重、factor_screen 的因子集）没有进入本框架，它们的过拟合风险未被本轮体检覆盖。
9. **OOS 与 IS 覆盖期不同**：验证窗只覆盖 S1 的一段，而全窗口 IS 含 2026 段；「衰减率(累计)」因此混合了过拟合效应与期间构成效应，**期间中性的判据是链式超额**（同期 gate 基准已扣除），判定逻辑也以它为准。
10. **复权口径不均匀**：最后一个可用月的行按未复权净收益进入回测（§1 第 4 条），与其余月份的复权口径不完全可比。

---

## 8. 附录：机器可读汇总（主切割聚合）

完整明细（含逐窗记录与敏感性切割）见同目录 `walk-forward-20260905.json`。

```json
{
  "backtest_run_count": 566,
  "db_path": "data\\moss.duckdb",
  "dedupe": {
    "deduped_matches_table_distinct_keys": true,
    "deduped_rows": 5833,
    "duplicate_keys": 14,
    "ema10_conflict_keys": 0,
    "join_fanout_rows": 14,
    "keep_rule": "ema10 非空优先，其次 ema10 最小，其次加载顺序首行",
    "key_fields": [
      "signal_date",
      "stock_code",
      "signal_kind"
    ],
    "loaded_rows": 5847,
    "max_multiplicity": 2,
    "removed_rows": 14,
    "removed_rows_by_kind": {
      "hybrid_fusion": 5,
      "mean_reversion": 4,
      "stock_candidate": 5
    },
    "table_distinct_keys": 5833,
    "table_duplicate_rows": 0,
    "table_rows_with_entry_date": 5833
  },
  "disclosure": {
    "dense_coverage_end": "2026-08-24",
    "first_uncovered_target_date": "",
    "last_uncovered_target_date": "",
    "max_factor_trade_date": "2026-08-24",
    "rows_after_dense_coverage_end": 0,
    "rows_with_uncovered_target": 0,
    "status": "ready",
    "uncovered_target_date_count": 0
  },
  "engine_version": "pbt_v2_path_mode",
  "execution_row_count": 5833,
  "generated_at": "2026-09-05 09:53:20+0800",
  "issues": [
    "执行历史加载行 5847 行去重为 5833 行（涉及 14 个 (signal_date, stock_code, signal_kind) 键）：ema10 join 扇出 14 行 + 表内完全重复 0 行；walk-forward 编排侧按键去重（保留 ema10 非空且最小者），不改共享加载器。",
    "Daily exposure source counts: missing=238, replayed=467",
    "238 dates lacked persisted or replayed gate exposure; portfolio uses state fallback for those dates."
  ],
  "mode": "path",
  "schedules": [
    {
      "equal_weight": {
        "factor_screen": {
          "decay_cagr": {
            "delta": null,
            "ratio": null,
            "status": "unavailable"
          },
          "decay_cumulative": {
            "delta": null,
            "ratio": null,
            "status": "unavailable"
          },
          "excess_sign_consistency": {
            "negative_windows": 0,
            "observed_windows": 0,
            "positive_ratio": null,
            "positive_windows": 0,
            "zero_windows": 0
          },
          "first_signal_date": "2026-04-30",
          "in_sample": {
            "buy_trades": 15,
            "cagr": -0.269402,
            "cumulative_return": -0.076863,
            "daily_sharpe": -1.493965,
            "excess_vs_gate": -0.026973,
            "gate_return": -0.04989,
            "input_rows": 1071,
            "max_drawdown": 0.126471,
            "skipped_missing_outcome": 0
          },
          "last_signal_date": "2026-07-10",
          "oos_annualized_return": null,
          "oos_chain_excess": null,
          "oos_chain_return": null,
          "oos_window_count": 0,
          "return_sign_consistency": {
            "negative_windows": 0,
            "observed_windows": 0,
            "positive_ratio": null,
            "positive_windows": 0,
            "zero_windows": 0
          },
          "total_usable_rows": 1071,
          "verdict": "insufficient_windows",
          "verdict_reason": "验证窗仅 0 个 (< 3)，自由度不足，不下结论"
        },
        "fresh_trend_watchlist": {
          "decay_cagr": {
            "delta": null,
            "ratio": null,
            "status": "unavailable"
          },
          "decay_cumulative": {
            "delta": null,
            "ratio": null,
            "status": "unavailable"
          },
          "excess_sign_consistency": {
            "negative_windows": 0,
            "observed_windows": 0,
            "positive_ratio": null,
            "positive_windows": 0,
            "zero_windows": 0
          },
          "first_signal_date": "2026-03-25",
          "in_sample": {
            "buy_trades": 20,
            "cagr": 0.471093,
            "cumulative_return": 0.14981,
            "daily_sharpe": 1.130855,
            "excess_vs_gate": 0.161914,
            "gate_return": -0.012104,
            "input_rows": 1180,
            "max_drawdown": 0.260323,
            "skipped_missing_outcome": 0
          },
          "last_signal_date": "2026-07-08",
          "oos_annualized_return": null,
          "oos_chain_excess": null,
          "oos_chain_return": null,
          "oos_window_count": 0,
          "return_sign_consistency": {
            "negative_windows": 0,
            "observed_windows": 0,
            "positive_ratio": null,
            "positive_windows": 0,
            "zero_windows": 0
          },
          "total_usable_rows": 1180,
          "verdict": "insufficient_windows",
          "verdict_reason": "验证窗仅 0 个 (< 3)，自由度不足，不下结论"
        },
        "hybrid_fusion": {
          "decay_cagr": {
            "delta": null,
            "ratio": null,
            "status": "unavailable"
          },
          "decay_cumulative": {
            "delta": null,
            "ratio": null,
            "status": "unavailable"
          },
          "excess_sign_consistency": {
            "negative_windows": 0,
            "observed_windows": 0,
            "positive_ratio": null,
            "positive_windows": 0,
            "zero_windows": 0
          },
          "first_signal_date": "2026-03-18",
          "in_sample": {
            "buy_trades": 20,
            "cagr": 0.002396,
            "cumulative_return": 0.000925,
            "daily_sharpe": 0.165232,
            "excess_vs_gate": 0.014795,
            "gate_return": -0.01387,
            "input_rows": 228,
            "max_drawdown": 0.215462,
            "skipped_missing_outcome": 0
          },
          "last_signal_date": "2026-07-10",
          "oos_annualized_return": null,
          "oos_chain_excess": null,
          "oos_chain_return": null,
          "oos_window_count": 0,
          "return_sign_consistency": {
            "negative_windows": 0,
            "observed_windows": 0,
            "positive_ratio": null,
            "positive_windows": 0,
            "zero_windows": 0
          },
          "total_usable_rows": 228,
          "verdict": "insufficient_windows",
          "verdict_reason": "验证窗仅 0 个 (< 3)，自由度不足，不下结论"
        },
        "mean_reversion": {
          "decay_cagr": {
            "delta": -0.078243,
            "ratio": -4.513932,
            "status": "ready"
          },
          "decay_cumulative": {
            "delta": -0.069499,
            "ratio": -1.616768,
            "status": "ready"
          },
          "excess_sign_consistency": {
            "negative_windows": 3,
            "observed_windows": 4,
            "positive_ratio": 0.25,
            "positive_windows": 1,
            "zero_windows": 0
          },
          "first_signal_date": "2024-09-24",
          "in_sample": {
            "buy_trades": 60,
            "cagr": 0.01419,
            "cumulative_return": 0.026559,
            "daily_sharpe": 0.163473,
            "excess_vs_gate": -0.198898,
            "gate_return": 0.225457,
            "input_rows": 602,
            "max_drawdown": 0.207731,
            "skipped_missing_outcome": 0
          },
          "last_signal_date": "2026-07-08",
          "oos_annualized_return": -0.064053,
          "oos_chain_excess": -0.116184,
          "oos_chain_return": -0.04294,
          "oos_window_count": 4,
          "return_sign_consistency": {
            "negative_windows": 2,
            "observed_windows": 4,
            "positive_ratio": 0.5,
            "positive_windows": 2,
            "zero_windows": 0
          },
          "total_usable_rows": 602,
          "verdict": "oos_weakened",
          "verdict_reason": "1/4 窗正超额，链式超额 -11.62%"
        },
        "stock_candidate": {
          "decay_cagr": {
            "delta": -0.312953,
            "ratio": null,
            "status": "is_non_positive"
          },
          "decay_cumulative": {
            "delta": -0.249929,
            "ratio": null,
            "status": "is_non_positive"
          },
          "excess_sign_consistency": {
            "negative_windows": 4,
            "observed_windows": 5,
            "positive_ratio": 0.2,
            "positive_windows": 1,
            "zero_windows": 0
          },
          "first_signal_date": "2024-09-24",
          "in_sample": {
            "buy_trades": 82,
            "cagr": -0.019796,
            "cumulative_return": -0.03535,
            "daily_sharpe": 0.091807,
            "excess_vs_gate": -0.305057,
            "gate_return": 0.269707,
            "input_rows": 770,
            "max_drawdown": 0.534813,
            "skipped_missing_outcome": 0
          },
          "last_signal_date": "2026-06-15",
          "oos_annualized_return": -0.332749,
          "oos_chain_excess": -0.542974,
          "oos_chain_return": -0.285279,
          "oos_window_count": 5,
          "return_sign_consistency": {
            "negative_windows": 5,
            "observed_windows": 5,
            "positive_ratio": 0.0,
            "positive_windows": 0,
            "zero_windows": 0
          },
          "total_usable_rows": 770,
          "verdict": "oos_weakened",
          "verdict_reason": "1/5 窗正超额，链式超额 -54.30%"
        },
        "theme_breakout": {
          "decay_cagr": {
            "delta": 1.957426,
            "ratio": 4.914366,
            "status": "ready"
          },
          "decay_cumulative": {
            "delta": 0.614443,
            "ratio": 1.518028,
            "status": "ready"
          },
          "excess_sign_consistency": {
            "negative_windows": 0,
            "observed_windows": 5,
            "positive_ratio": 1.0,
            "positive_windows": 5,
            "zero_windows": 0
          },
          "first_signal_date": "2024-08-30",
          "in_sample": {
            "buy_trades": 84,
            "cagr": 0.500062,
            "cumulative_return": 1.186119,
            "daily_sharpe": 1.3243,
            "excess_vs_gate": 0.937007,
            "gate_return": 0.249112,
            "input_rows": 559,
            "max_drawdown": 0.262649,
            "skipped_missing_outcome": 0
          },
          "last_signal_date": "2026-07-10",
          "oos_annualized_return": 2.457488,
          "oos_chain_excess": 1.541298,
          "oos_chain_return": 1.800562,
          "oos_window_count": 5,
          "return_sign_consistency": {
            "negative_windows": 0,
            "observed_windows": 5,
            "positive_ratio": 1.0,
            "positive_windows": 5,
            "zero_windows": 0
          },
          "total_usable_rows": 559,
          "verdict": "oos_supported",
          "verdict_reason": "5/5 窗正超额且链式超额 +154.13%"
        },
        "uptrend_momentum": {
          "decay_cagr": {
            "delta": null,
            "ratio": null,
            "status": "unavailable"
          },
          "decay_cumulative": {
            "delta": null,
            "ratio": null,
            "status": "unavailable"
          },
          "excess_sign_consistency": {
            "negative_windows": 0,
            "observed_windows": 0,
            "positive_ratio": null,
            "positive_windows": 0,
            "zero_windows": 0
          },
          "first_signal_date": "2026-03-25",
          "in_sample": {
            "buy_trades": 20,
            "cagr": 0.217556,
            "cumulative_return": 0.073783,
            "daily_sharpe": 0.76171,
            "excess_vs_gate": 0.085887,
            "gate_return": -0.012104,
            "input_rows": 1200,
            "max_drawdown": 0.254422,
            "skipped_missing_outcome": 0
          },
          "last_signal_date": "2026-07-08",
          "oos_annualized_return": null,
          "oos_chain_excess": null,
          "oos_chain_return": null,
          "oos_window_count": 0,
          "return_sign_consistency": {
            "negative_windows": 0,
            "observed_windows": 0,
            "positive_ratio": null,
            "positive_windows": 0,
            "zero_windows": 0
          },
          "total_usable_rows": 1200,
          "verdict": "insufficient_windows",
          "verdict_reason": "验证窗仅 0 个 (< 3)，自由度不足，不下结论"
        }
      },
      "risk_budget": {
        "factor_screen": {
          "drift": {
            "distinct_values": 0,
            "mean_abs_step": null,
            "mode_share": null,
            "mode_value": null,
            "observed_windows": 0,
            "switch_count": null,
            "switch_rate": null
          },
          "fixed_policy": {
            "decay_cagr": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "decay_cumulative": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 0,
              "positive_ratio": null,
              "positive_windows": 0,
              "zero_windows": 0
            },
            "oos_annualized_return": null,
            "oos_chain_excess": null,
            "oos_chain_return": null,
            "oos_total_span_days": 0,
            "oos_window_count": 0,
            "verdict": "insufficient_windows"
          },
          "grid": [
            0.0025,
            0.005,
            0.0075,
            0.01
          ],
          "in_sample_selection": 0.01,
          "oracle": {
            "decay_cagr": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "decay_cumulative": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 0,
              "positive_ratio": null,
              "positive_windows": 0,
              "zero_windows": 0
            },
            "oos_annualized_return": null,
            "oos_chain_excess": null,
            "oos_chain_return": null,
            "oos_total_span_days": 0,
            "oos_window_count": 0,
            "verdict": "insufficient_windows"
          },
          "policy_in_sample": {
            "buy_trades": 15,
            "cagr": -0.106926,
            "cumulative_return": -0.028403,
            "daily_sharpe": -1.469019,
            "excess_vs_gate": 0.021487,
            "gate_return": -0.04989,
            "input_rows": 1071,
            "max_drawdown": 0.048612,
            "skipped_missing_outcome": 0
          },
          "policy_param": 0.005,
          "selected": {
            "decay_cagr": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "decay_cumulative": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 0,
              "positive_ratio": null,
              "positive_windows": 0,
              "zero_windows": 0
            },
            "oos_annualized_return": null,
            "oos_chain_excess": null,
            "oos_chain_return": null,
            "oos_total_span_days": 0,
            "oos_window_count": 0,
            "verdict": "insufficient_windows"
          }
        },
        "fresh_trend_watchlist": {
          "drift": {
            "distinct_values": 0,
            "mean_abs_step": null,
            "mode_share": null,
            "mode_value": null,
            "observed_windows": 0,
            "switch_count": null,
            "switch_rate": null
          },
          "fixed_policy": {
            "decay_cagr": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "decay_cumulative": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 0,
              "positive_ratio": null,
              "positive_windows": 0,
              "zero_windows": 0
            },
            "oos_annualized_return": null,
            "oos_chain_excess": null,
            "oos_chain_return": null,
            "oos_total_span_days": 0,
            "oos_window_count": 0,
            "verdict": "insufficient_windows"
          },
          "grid": [
            0.0025,
            0.005,
            0.0075,
            0.01
          ],
          "in_sample_selection": 0.01,
          "oracle": {
            "decay_cagr": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "decay_cumulative": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 0,
              "positive_ratio": null,
              "positive_windows": 0,
              "zero_windows": 0
            },
            "oos_annualized_return": null,
            "oos_chain_excess": null,
            "oos_chain_return": null,
            "oos_total_span_days": 0,
            "oos_window_count": 0,
            "verdict": "insufficient_windows"
          },
          "policy_in_sample": {
            "buy_trades": 20,
            "cagr": 0.238065,
            "cumulative_return": 0.080289,
            "daily_sharpe": 1.091196,
            "excess_vs_gate": 0.092393,
            "gate_return": -0.012104,
            "input_rows": 1180,
            "max_drawdown": 0.165699,
            "skipped_missing_outcome": 0
          },
          "policy_param": 0.005,
          "selected": {
            "decay_cagr": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "decay_cumulative": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 0,
              "positive_ratio": null,
              "positive_windows": 0,
              "zero_windows": 0
            },
            "oos_annualized_return": null,
            "oos_chain_excess": null,
            "oos_chain_return": null,
            "oos_total_span_days": 0,
            "oos_window_count": 0,
            "verdict": "insufficient_windows"
          }
        },
        "hybrid_fusion": {
          "drift": {
            "distinct_values": 0,
            "mean_abs_step": null,
            "mode_share": null,
            "mode_value": null,
            "observed_windows": 0,
            "switch_count": null,
            "switch_rate": null
          },
          "fixed_policy": {
            "decay_cagr": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "decay_cumulative": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 0,
              "positive_ratio": null,
              "positive_windows": 0,
              "zero_windows": 0
            },
            "oos_annualized_return": null,
            "oos_chain_excess": null,
            "oos_chain_return": null,
            "oos_total_span_days": 0,
            "oos_window_count": 0,
            "verdict": "insufficient_windows"
          },
          "grid": [
            0.0025,
            0.005,
            0.0075,
            0.01
          ],
          "in_sample_selection": 0.0025,
          "oracle": {
            "decay_cagr": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "decay_cumulative": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 0,
              "positive_ratio": null,
              "positive_windows": 0,
              "zero_windows": 0
            },
            "oos_annualized_return": null,
            "oos_chain_excess": null,
            "oos_chain_return": null,
            "oos_total_span_days": 0,
            "oos_window_count": 0,
            "verdict": "insufficient_windows"
          },
          "policy_in_sample": {
            "buy_trades": 20,
            "cagr": -0.049524,
            "cumulative_return": -0.01943,
            "daily_sharpe": -0.225058,
            "excess_vs_gate": -0.00556,
            "gate_return": -0.01387,
            "input_rows": 228,
            "max_drawdown": 0.135874,
            "skipped_missing_outcome": 0
          },
          "policy_param": 0.005,
          "selected": {
            "decay_cagr": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "decay_cumulative": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 0,
              "positive_ratio": null,
              "positive_windows": 0,
              "zero_windows": 0
            },
            "oos_annualized_return": null,
            "oos_chain_excess": null,
            "oos_chain_return": null,
            "oos_total_span_days": 0,
            "oos_window_count": 0,
            "verdict": "insufficient_windows"
          }
        },
        "mean_reversion": {
          "drift": {
            "distinct_values": 2,
            "mean_abs_step": 0.00125,
            "mode_share": 0.6,
            "mode_value": 0.0075,
            "observed_windows": 5,
            "switch_count": 2,
            "switch_rate": 0.5
          },
          "fixed_policy": {
            "decay_cagr": {
              "delta": -0.03628,
              "ratio": 0.325433,
              "status": "ready"
            },
            "decay_cumulative": {
              "delta": -0.090789,
              "ratio": 0.113039,
              "status": "ready"
            },
            "excess_sign_consistency": {
              "negative_windows": 3,
              "observed_windows": 4,
              "positive_ratio": 0.25,
              "positive_windows": 1,
              "zero_windows": 0
            },
            "oos_annualized_return": 0.017503,
            "oos_chain_excess": -0.061674,
            "oos_chain_return": 0.011571,
            "oos_total_span_days": 242,
            "oos_window_count": 4,
            "verdict": "oos_weakened"
          },
          "grid": [
            0.0025,
            0.005,
            0.0075,
            0.01
          ],
          "in_sample_selection": 0.01,
          "oracle": {
            "decay_cagr": {
              "delta": 0.011493,
              "ratio": 1.21369,
              "status": "ready"
            },
            "decay_cumulative": {
              "delta": -0.059544,
              "ratio": 0.41829,
              "status": "ready"
            },
            "excess_sign_consistency": {
              "negative_windows": 3,
              "observed_windows": 4,
              "positive_ratio": 0.25,
              "positive_windows": 1,
              "zero_windows": 0
            },
            "oos_annualized_return": 0.065276,
            "oos_chain_excess": -0.030428,
            "oos_chain_return": 0.042816,
            "oos_total_span_days": 242,
            "oos_window_count": 4,
            "verdict": "oos_weakened"
          },
          "policy_in_sample": {
            "buy_trades": 60,
            "cagr": 0.053783,
            "cumulative_return": 0.10236,
            "daily_sharpe": 0.575423,
            "excess_vs_gate": -0.123097,
            "gate_return": 0.225457,
            "input_rows": 602,
            "max_drawdown": 0.093087,
            "skipped_missing_outcome": 0
          },
          "policy_param": 0.005,
          "selected": {
            "decay_cagr": {
              "delta": 0.02063,
              "ratio": 1.383587,
              "status": "ready"
            },
            "decay_cumulative": {
              "delta": -0.053622,
              "ratio": 0.476145,
              "status": "ready"
            },
            "excess_sign_consistency": {
              "negative_windows": 3,
              "observed_windows": 4,
              "positive_ratio": 0.25,
              "positive_windows": 1,
              "zero_windows": 0
            },
            "oos_annualized_return": 0.074413,
            "oos_chain_excess": -0.024506,
            "oos_chain_return": 0.048738,
            "oos_total_span_days": 242,
            "oos_window_count": 4,
            "verdict": "oos_weakened"
          }
        },
        "stock_candidate": {
          "drift": {
            "distinct_values": 3,
            "mean_abs_step": 0.003125,
            "mode_share": 0.6,
            "mode_value": 0.0025,
            "observed_windows": 5,
            "switch_count": 2,
            "switch_rate": 0.5
          },
          "fixed_policy": {
            "decay_cagr": {
              "delta": -0.115756,
              "ratio": -0.346799,
              "status": "ready"
            },
            "decay_cumulative": {
              "delta": -0.184804,
              "ratio": -0.155049,
              "status": "ready"
            },
            "excess_sign_consistency": {
              "negative_windows": 4,
              "observed_windows": 5,
              "positive_ratio": 0.2,
              "positive_windows": 1,
              "zero_windows": 0
            },
            "oos_annualized_return": -0.029807,
            "oos_chain_excess": -0.282502,
            "oos_chain_return": -0.024807,
            "oos_total_span_days": 303,
            "oos_window_count": 5,
            "verdict": "oos_weakened"
          },
          "grid": [
            0.0025,
            0.005,
            0.0075,
            0.01
          ],
          "in_sample_selection": 0.0025,
          "oracle": {
            "decay_cagr": {
              "delta": -0.190396,
              "ratio": -1.215219,
              "status": "ready"
            },
            "decay_cumulative": {
              "delta": -0.247505,
              "ratio": -0.546933,
              "status": "ready"
            },
            "excess_sign_consistency": {
              "negative_windows": 4,
              "observed_windows": 5,
              "positive_ratio": 0.2,
              "positive_windows": 1,
              "zero_windows": 0
            },
            "oos_annualized_return": -0.104447,
            "oos_chain_excess": -0.345202,
            "oos_chain_return": -0.087508,
            "oos_total_span_days": 303,
            "oos_window_count": 5,
            "verdict": "oos_weakened"
          },
          "policy_in_sample": {
            "buy_trades": 82,
            "cagr": 0.085949,
            "cumulative_return": 0.159997,
            "daily_sharpe": 0.901618,
            "excess_vs_gate": -0.10971,
            "gate_return": 0.269707,
            "input_rows": 770,
            "max_drawdown": 0.140079,
            "skipped_missing_outcome": 0
          },
          "policy_param": 0.005,
          "selected": {
            "decay_cagr": {
              "delta": -0.086316,
              "ratio": -0.004269,
              "status": "ready"
            },
            "decay_cumulative": {
              "delta": -0.160302,
              "ratio": -0.001904,
              "status": "ready"
            },
            "excess_sign_consistency": {
              "negative_windows": 4,
              "observed_windows": 5,
              "positive_ratio": 0.2,
              "positive_windows": 1,
              "zero_windows": 0
            },
            "oos_annualized_return": -0.000367,
            "oos_chain_excess": -0.257999,
            "oos_chain_return": -0.000305,
            "oos_total_span_days": 303,
            "oos_window_count": 5,
            "verdict": "oos_weakened"
          }
        },
        "theme_breakout": {
          "drift": {
            "distinct_values": 3,
            "mean_abs_step": 0.001875,
            "mode_share": 0.6,
            "mode_value": 0.01,
            "observed_windows": 5,
            "switch_count": 2,
            "switch_rate": 0.5
          },
          "fixed_policy": {
            "decay_cagr": {
              "delta": 0.480426,
              "ratio": 3.294387,
              "status": "ready"
            },
            "decay_cumulative": {
              "delta": 0.102791,
              "ratio": 1.232057,
              "status": "ready"
            },
            "excess_sign_consistency": {
              "negative_windows": 1,
              "observed_windows": 5,
              "positive_ratio": 0.8,
              "positive_windows": 4,
              "zero_windows": 0
            },
            "oos_annualized_return": 0.689818,
            "oos_chain_excess": 0.286483,
            "oos_chain_return": 0.545747,
            "oos_total_span_days": 303,
            "oos_window_count": 5,
            "verdict": "oos_supported"
          },
          "grid": [
            0.0025,
            0.005,
            0.0075,
            0.01
          ],
          "in_sample_selection": 0.0075,
          "oracle": {
            "decay_cagr": {
              "delta": 1.371508,
              "ratio": 7.549955,
              "status": "ready"
            },
            "decay_cumulative": {
              "delta": 0.754026,
              "ratio": 2.702259,
              "status": "ready"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 5,
              "positive_ratio": 1.0,
              "positive_windows": 5,
              "zero_windows": 0
            },
            "oos_annualized_return": 1.5809,
            "oos_chain_excess": 0.937718,
            "oos_chain_return": 1.196982,
            "oos_total_span_days": 303,
            "oos_window_count": 5,
            "verdict": "oos_supported"
          },
          "policy_in_sample": {
            "buy_trades": 84,
            "cagr": 0.209392,
            "cumulative_return": 0.442956,
            "daily_sharpe": 1.28157,
            "excess_vs_gate": 0.193844,
            "gate_return": 0.249112,
            "input_rows": 559,
            "max_drawdown": 0.149684,
            "skipped_missing_outcome": 0
          },
          "policy_param": 0.005,
          "selected": {
            "decay_cagr": {
              "delta": 0.951315,
              "ratio": 5.543227,
              "status": "ready"
            },
            "decay_cumulative": {
              "delta": 0.452704,
              "ratio": 2.022007,
              "status": "ready"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 5,
              "positive_ratio": 1.0,
              "positive_windows": 5,
              "zero_windows": 0
            },
            "oos_annualized_return": 1.160707,
            "oos_chain_excess": 0.636396,
            "oos_chain_return": 0.89566,
            "oos_total_span_days": 303,
            "oos_window_count": 5,
            "verdict": "oos_supported"
          }
        },
        "uptrend_momentum": {
          "drift": {
            "distinct_values": 0,
            "mean_abs_step": null,
            "mode_share": null,
            "mode_value": null,
            "observed_windows": 0,
            "switch_count": null,
            "switch_rate": null
          },
          "fixed_policy": {
            "decay_cagr": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "decay_cumulative": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 0,
              "positive_ratio": null,
              "positive_windows": 0,
              "zero_windows": 0
            },
            "oos_annualized_return": null,
            "oos_chain_excess": null,
            "oos_chain_return": null,
            "oos_total_span_days": 0,
            "oos_window_count": 0,
            "verdict": "insufficient_windows"
          },
          "grid": [
            0.0025,
            0.005,
            0.0075,
            0.01
          ],
          "in_sample_selection": 0.01,
          "oracle": {
            "decay_cagr": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "decay_cumulative": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 0,
              "positive_ratio": null,
              "positive_windows": 0,
              "zero_windows": 0
            },
            "oos_annualized_return": null,
            "oos_chain_excess": null,
            "oos_chain_return": null,
            "oos_total_span_days": 0,
            "oos_window_count": 0,
            "verdict": "insufficient_windows"
          },
          "policy_in_sample": {
            "buy_trades": 20,
            "cagr": 0.116645,
            "cumulative_return": 0.040706,
            "daily_sharpe": 0.721011,
            "excess_vs_gate": 0.05281,
            "gate_return": -0.012104,
            "input_rows": 1200,
            "max_drawdown": 0.1497,
            "skipped_missing_outcome": 0
          },
          "policy_param": 0.005,
          "selected": {
            "decay_cagr": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "decay_cumulative": {
              "delta": null,
              "ratio": null,
              "status": "unavailable"
            },
            "excess_sign_consistency": {
              "negative_windows": 0,
              "observed_windows": 0,
              "positive_ratio": null,
              "positive_windows": 0,
              "zero_windows": 0
            },
            "oos_annualized_return": null,
            "oos_chain_excess": null,
            "oos_chain_return": null,
            "oos_total_span_days": 0,
            "oos_window_count": 0,
            "verdict": "insufficient_windows"
          }
        }
      },
      "schedule": {
        "detailed": true,
        "label": "primary_6t_2v_2s",
        "min_windows_for_verdict": 3,
        "objective": "sharpe",
        "purge_enabled": true,
        "step_months": 2,
        "train_months": 6,
        "valid_months": 2
      },
      "segments": [
        {
          "end_date": "2025-12-31",
          "segment_id": "S1",
          "signal_date_count": 249,
          "start_date": "2024-08-30",
          "start_reason": "series_start"
        },
        {
          "end_date": "2026-07-10",
          "segment_id": "S2",
          "signal_date_count": 65,
          "start_date": "2026-03-18",
          "start_reason": "forced_cut:2026-01-05+data_gap:77d"
        }
      ],
      "windows": [
        {
          "segment_id": "S1",
          "train_end": "2025-01-31",
          "train_start": "2024-08-01",
          "valid_end": "2025-03-31",
          "valid_end_clamped": false,
          "valid_start": "2025-02-01",
          "window_id": "S1W1"
        },
        {
          "segment_id": "S1",
          "train_end": "2025-03-31",
          "train_start": "2024-10-01",
          "valid_end": "2025-05-31",
          "valid_end_clamped": false,
          "valid_start": "2025-04-01",
          "window_id": "S1W2"
        },
        {
          "segment_id": "S1",
          "train_end": "2025-05-31",
          "train_start": "2024-12-01",
          "valid_end": "2025-07-31",
          "valid_end_clamped": false,
          "valid_start": "2025-06-01",
          "window_id": "S1W3"
        },
        {
          "segment_id": "S1",
          "train_end": "2025-07-31",
          "train_start": "2025-02-01",
          "valid_end": "2025-09-30",
          "valid_end_clamped": false,
          "valid_start": "2025-08-01",
          "window_id": "S1W4"
        },
        {
          "segment_id": "S1",
          "train_end": "2025-09-30",
          "train_start": "2025-04-01",
          "valid_end": "2025-11-30",
          "valid_end_clamped": false,
          "valid_start": "2025-10-01",
          "window_id": "S1W5"
        }
      ],
      "windows_crossing_forced_cut": {},
      "windows_disjoint": true,
      "windows_valid_end_clamped": {}
    }
  ],
  "usable_row_count": 5610
}
```
