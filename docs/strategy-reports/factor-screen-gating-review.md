# factor_screen 市场状态门控复审决策报告（治理蓝本 P1 项）

- 日期：2026-08-12
- 性质：只读审计与门控模拟，未修改任何生产代码与数据
- 复算引擎：临时旁路脚本（已删除），DuckDB `data/moss.duckdb` 只读
- 上游蓝本：`tmp-strategy-reports/factor-screen-remediation.md`（P0 流动性地板已落地为 v3，本报告为其 P1 项"市场状态门控复审"）
- 审计人：calc-audit-macro-strategy（策略计算端审计）

---

## 0. 执行摘要

**结论：推荐方案 b（收紧为 {WARM, HOT, OVERHEAT}，仅剔 OFF）+ 把"声明但未执行"的门控变为强制检查，定位为语义收口而非收益修复（预期收益影响 ≈ 0）。不推荐方案 a（收紧到 WARM/HOT）：其窗口内 +0.6~1.1pp 的表面改善在状态标签换用当前供数重放后完全消失，是标签巧合而非稳健状态效应。方案 c（gate 敞口缩放）经代码取证已是官方回测现状，无需实施；信号闸门与敞口闸门作用于不同层，仅在 OFF 态重叠，对 OVERHEAT 收紧不构成"双重收缩"。**

五个改变问题框架的事实发现：

1. **OVERHEAT 不是"要求空仓/收缩"的状态。** 门控状态机（`livermore_strategy.py`）定义 OVERHEAT = 4 条条件全过 = 最强趋势读数，`exposure_by_market_state` 给它的敞口是 **1.0（满仓）**；要求收缩的只有 OFF（0~0.25）。OVERHEAT 下暂停的是趋势族的**新入场信号**（防拥挤追顶），不是持仓敞口。治理蓝本 P1 条目"OFF/OVERHEAT 在场=门控要求空仓/收缩下满额输出"的表述只对 OFF 一半成立。
2. **factor_screen 的 active_states 是"声明但无执行点"的空转字段。** `compute_factor_screen_candidates` 显式忽略 `market_state`（`factor_screen_candidates.py:46`），服务层无条件调用（`market_data_livermore_service.py:1823`）。现状与集合恰好覆盖全部活跃状态相容，但一旦收紧，必须先补执行点；且当前连 NO_DATA/STALE/PENDING_DATA 也不拦。
3. **执行历史 38 个信号日中 0 个 OFF 日；近两年重放序列 OFF 仅 1/469 天。** 方案 b 在观测期内零行损失、零收益影响——它修正的是语义矛盾（门控 0/4 条件、敞口 0~0.25 时仍产新候选），不是回撤。实时语义下 OFF 并非不存在（theme_breakout 执行历史录得 16 个 OFF 信号日），熊市/供数缺失时会重现。
4. **方案 a 的改善不稳健（本报告最重要的模拟结论）。** 按执行历史记录状态：剔除 OVERHEAT 561 行（−5.84%）后保留组 −4.69%，改善 +0.64pp；但把状态换成当前供数的重放标签后，保留组 −5.36% vs 剔除组 −5.25%，**改善归零并轻微反向**。原因：12/38 个信号日的状态在广度供数修订后已漂移（9 个 OVERHEAT→HOT），最差的一段（05-26~06-01，日均 −6.5%~−10.2%）恰好从"被剔除"漂到"被保留"。
5. **市场状态标签系统性不可复现（High 治理发现）。** `load_gate_exposure_by_date` 的三张持久化表（`livermore_monitor_append`/`livermore_gate_history`/`livermore_gate_supplement`）全部不存在，官方回测的逐日敞口 **100% 来自重放**；theme_breakout 16 个记录 OFF 日重放一致率 **0/16**，stock_candidate 231 个信号日漂移率 **41%**。任何状态条件化的回测、门控变更验证、快照测试都建立在会漂移的标签上——这是任何 active_states 变更的验证前置问题。

**方案模拟汇总**（20d 净收益、每笔等权口径；治理窗口 1011 行/34 信号日）：

| 方案 | 保留 | 池化均值 | Δ vs 基线 | 备注 |
|---|---|---|---|---|
| 基线（现状全在场） | 1011 行/34 日 | −5.33% | — | 与蓝本 P0 冻结名单 −5.31% 自洽 |
| a 收紧 WARM/HOT | 450 行/15 日 | −4.69% | +0.64pp | **重放状态下改善消失（−0.11pp）**；损失 55% 行数 |
| b 仅剔 OFF | 1011 行/34 日 | −5.33% | 0 | 观测期无 OFF 日，纯语义修正 |
| c gate 敞口缩放 | 1011 行（平均敞口 0.80） | −4.29%（资本缩放口径） | +1.04pp | **已是官方回测现状**，非新方案 |
| a+c 叠加 | 450 行缩放 | −3.40% | +1.93pp | 证明 a 与 c 互补而非重复 |
| d OVERHEAT 仅留 rank≤10 | 640 行/34 日 | −5.19% | +0.14pp | 无意义；且 rank 证据与既有诊断规则方向相反 |

统计力如实披露：34 个信号日跨约 36 个交易日，20d 持有期重叠，**不重叠的独立观测 ≈ 2 个**；全部 Δ 均在单一区制噪声内，只能作方向参考，不构成统计证据。

---

## 1. 审计范围与复算口径

### 1.1 数据源（全部只读）

| 表 | 用途 |
|---|---|
| `livermore_candidate_execution_history` | factor_screen 冻结名单 1131 行/38 信号日（2026-04-30~07-24），其中治理窗口（≤06-22）1011 行/34 日；每行带信号日实时 `market_state` |
| `choice_stock_daily_observation` | 631 交易日全市场行情（2024-01-02~2026-08-11），20d/5d 收益重算 |
| `stock_adjustment_factor` | 双复权（覆盖 2024-08-30~2026-07-21；同日多 run 取 `run_id desc, source_version desc` 首行） |
| `fact_choice_macro_daily`（CA.CSI300）+ `fact_livermore_gate_supplement_daily` | 市场门控逐日重放输入（经 `gate_exposure_series.load_gate_exposure_by_date`，与官方回测同函数） |

### 1.2 收益重算口径（对齐正式执行引擎）

严格复刻 `livermore_candidate_history_materialize._execution_returns_for_candidate`：bars=信号日后 close 非空的全部 bar；入场=bars[0] 开盘价（缺开盘退化收盘），halt/一字涨停（entry≥highlimit×0.999）阻断；出场=bars[19]（20d）/bars[4]（5d）起第一根可卖 bar（跳过 halt/跌停/close 空）收盘；`adj_factor` 精确日期双复权；净收益 `(1+gross)×(1−0.0041)−1`。

**保真度自检**：与表内已回填值对照，20d 可比 408 行 mean|diff| = **0.00047**（max 0.0023），5d 可比 857 行 mean|diff| = 0.00026——与蓝本 §1.3 的 0.0005 一致，复刻成立。

**为什么必须重算而非直接用表内值**：执行历史 20d 收益物化冻结未回填，1131 行仅 408 行有 `return_20d_net_adj`（2026-06-10 后全部 pending），且缺失沿状态分布极端不均——**WARM 状态 0 行有官方 20d 值**。直接用表内值做分状态对比会把 WARM 整层从样本中抹掉（蓝本发现 L1 的门控版后果）。

**复权回退披露**：正式引擎要求 entry/exit 精确日期的 adj_factor 行、缺失即置 None；本审计为覆盖全部行，缺失时回退未复权收益并计数：治理窗口 411 行精确复权 / 600 行回退（复权表为稀疏落行，非逐日全量），全历史另有 60 行（07-21/24 两日）20d 视界截断。回退行在无除权事件时零误差（5d 口径 mean|diff|=0.00026 印证总体无偏，max 0.048 提示个别行含除权误差）；方案间 Δ 为同批行的分组比较，对回退口径中性，结论稳健。

---

## 2. 现状精确化

### 2.1 各 signal_kind 的 active_states 对照表（读 `strategy_policy.py` sp_v1 + 模块常量 + 执行历史实证）

| signal_kind | active_states | 定义位置 | 执行点 | OFF | OVERHEAT | 执行历史实证（状态：行/日） |
|---|---|---|---|---|---|---|
| stock_candidate·default | {WARM, HOT, OVERHEAT} | `strategy_policy.py:110`（POLICY 字段） | `livermore_stock_candidates.py:89` | 停 | 在场 | WARM 281/71、HOT 342/86、OVERHEAT 193/74 |
| stock_candidate·exp3b / exp3c_shadow | {WARM, HOT} | `strategy_policy.py:120/129` | 同上 | 停 | 停 | —（实验档） |
| uptrend_momentum | {WARM, HOT} | `uptrend_momentum_candidates.py:12`（模块字面量） | 同文件 :52 | 停 | 停 | WARM 531/18、HOT 720/24 ✓ |
| fresh_trend_watchlist | {WARM, HOT, OVERHEAT} | `fresh_trend_watchlist_candidates.py:12`（模块字面量） | 同文件 :88 | 停 | 在场 | WARM 334/18、HOT 480/24、OVERHEAT 380/19 |
| mean_reversion | {WARM} | `strategy_policy.py:149`（POLICY 字段） | `mean_reversion_candidates.py:44` | 停 | 停 | WARM 640/82 ✓ |
| hybrid_fusion | {WARM, HOT} | `strategy_policy.py:150`（POLICY 字段） | `hybrid_fusion_candidates.py:55` | 停 | 停 | WARM 100/19、HOT 153/18 ✓ |
| theme_breakout | 无门控 | — | 无 | 在场 | 在场 | 含 **OFF 92/16**、OVERHEAT 131/25 |
| **factor_screen** | **{OFF, WARM, HOT, OVERHEAT}** | `strategy_policy.py:151`（POLICY 字段） | **无**（`factor_screen_candidates.py:46` 显式 `_ = market_state`；服务层 `market_data_livermore_service.py:1823` 无条件调用） | 在场 | 在场 | WARM 180/6、HOT 390/13、OVERHEAT 561/19、OFF 0 |

要点：

- factor_screen 是 POLICY 字段中唯一**声明后无执行点**的门控。`ACTIVE_MARKET_STATES`（`factor_screen_candidates.py:14`）仅被 `test_strategy_policy.py:239` 的 identity 断言消费。收紧集合本身不会改变任何行为，必须同时补状态检查。
- 副作用：兄弟策略的状态检查天然拦截 NO_DATA/STALE/PENDING_DATA（不在各自集合内），factor_screen 连这三个非活跃态也不拦——快照可用而门控无数据时照常产候选（观测期内未实际发生，latent 语义洞）。
- entry_observation_states={WARM,HOT}（`strategy_policy.py:148`）另被候选历史侧的组合代理/官方组合回测用作 stock_candidate 行过滤（`livermore_candidate_history_service.py:179-182`），与信号生成层的 active_states 是两个消费面。

### 2.2 门控状态机与两层闸门语义（厘清"双重收缩"前提）

**状态机**（`livermore_strategy.py:30-180`）：4 条腿——CSI300 close>MA60、CSI300 MA20>MA60、5 日广度>0、涨停封板质量正；`passed=0→OFF；passed=4→OVERHEAT；≥3→HOT；1~2→WARM`（可用<4 条时趋势全败→OFF、否则 WARM）。**逐日敞口 = passed/4**（:158），状态阶梯 `exposure_by_market_state`：OFF (0,0.25)、WARM (0.25,0.5,0.75)、HOT (0.75,)、**OVERHEAT (1.0,)**。

| 层 | 载体 | 作用点 | OFF | WARM | HOT | OVERHEAT |
|---|---|---|---|---|---|---|
| ① 信号生成闸门 | `*_active_states` + core 层检查 | 是否产出候选（页面/台账/fusion 供票） | 因策略而异 | 全在场 | 全在场 | 趋势敏感策略停 |
| ② 仓位敞口闸门 | `exposure_by_market_state` + 逐日 gate 敞口 | 回测/sizing 的**新入场资金规模** | 0~0.25 | 0.25~0.75 | 0.75 | **1.0（满仓）** |

**两层仅在 OFF 同时收缩**（信号停 + 敞口≈0）；在 OVERHEAT，敞口层是满仓，信号闸门是唯一的收缩手段。因此"对 OVERHEAT 收紧信号闸门 + 保留敞口层"不构成双重收缩；真正的语义重叠只有 OFF——而这正是方案 b 要收口的状态。

**方案 c 已是现状的代码取证**：官方回测脚本 `scripts/run_portfolio_backtest.py` 以 `exposure_basis=per-date` 调用 `load_gate_exposure_by_date`（:27/:132）取逐日门控敞口传入引擎；`portfolio_backtest.py:481-512` 在入场时按 T-1 敞口缩放新仓（等权 sizing `target=equity×exposure/max_positions`；risk_budget 按 `equity×exposure` 预算截断；`exposure≤0` 直接 skip）。蓝本引用的官方 −8.7%（path 模式）**已经包含 gate 敞口缩放**——它没能保护的原因是该窗口门控自己读数 HOT/OVERHEAT（敞口 0.75~1.0），而非缺少敞口机制。

### 2.3 执行历史按信号日市场状态分布与收益

**行/日分布**（factor_screen 全历史 1131 行/38 日；治理窗口 1011 行/34 日）：

| 状态 | 治理窗口 | 全历史 | 时代交易日分布（重放，2026-04-30~07-24 共 58 日） | 长窗口重放频率（2024-09-02~2026-08-11，469 交易日） |
|---|---|---|---|---|
| OFF | 0 行/0 日 | 0 行/0 日 | 0 日 | **1 日（0.2%）**（2025-01-10） |
| WARM | 60 行/2 日 | 180 行/6 日 | 15 日 | 163 日（34.8%） |
| HOT | 390 行/13 日 | 390 行/13 日 | 31 日 | 153 日（32.6%） |
| OVERHEAT | 561 行/19 日 | 561 行/19 日 | 12 日 | 152 日（32.4%） |

**分状态 20d 净收益（重算，治理窗口）**：

| 状态（记录） | 日/行 | mean | median | p10 | p25 | p75 | p90 | min | 胜率 | 按日等权 | CSI300 同日 20d 前瞻 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| WARM | 2/60 | −4.02% | −5.88% | −13.63% | −9.96% | −1.48% | +5.04% | −17.42% | 20.0% | −4.02% | +1.45% |
| HOT | 13/390 | −4.79% | −6.53% | −15.07% | −10.88% | −1.44% | +5.95% | −33.46% | 19.2% | −4.79% | +0.63% |
| OVERHEAT | 19/561 | −5.84% | −7.22% | −17.49% | −12.99% | −1.36% | +6.10% | −35.12% | 21.4% | −5.80% | −1.93% |

**分状态 5d 净收益（治理窗口）**：WARM −0.57%（胜率 45.0%）、HOT −2.24%（27.7%）、OVERHEAT −2.55%（24.4%）。

全历史口径下 WARM 扩展到 6 日/180 行（20d 可算 4 日/120 行，07-21/24 截断）：20d mean −0.05%、胜率 46.7%；5d mean +1.30%、胜率 67.2%——由 7 月修复行情拉动，进一步说明分状态读数由所处时段主导（§3.1 敏感性）。

**表面排序 OVERHEAT < HOT < WARM 与门控预期完全倒挂**：门控读数越强（OVERHEAT=四腿全绿、敞口满仓），随后 20 天越差，连 CSI300 自身在 OVERHEAT 信号日后 20d 平均 −1.93%。机制：本时代 CSI300 长期在 MA60 上方（趋势两腿常绿）+ 涨停质量腿长期为 True，状态主要由广度腿单腿摆动；广度转正的日子恰是小盘反弹末端，"四腿全绿"成为局部顶部指纹。但该倒挂不稳健（§3.1），不能作为收紧依据。

---

## 3. 收紧方案模拟（真实数据）

### 3.1 方案 a：收紧到 {WARM, HOT}（对齐 uptrend）

**记录状态口径**（执行历史实时标签，= 未来实盘门控语义）：

| 组 | 行/日 | 20d 池化 | 20d 按日等权 | 分布 |
|---|---|---|---|---|
| 保留 WARM/HOT | 450/15 | **−4.69%** | −4.69% | 胜率 19.3% |
| 剔除 OVERHEAT | 561/19 | **−5.84%** | −5.80% | med −7.22%、p10 −17.49%、p25 −12.99%、min −35.12%、胜率 21.4% |

- 信号损失：治理窗口剔 55.5% 行数/19 日；全历史剔 49.6% 行/19 日；长窗口重放频率下未来约剔 **32% 的交易日**。
- 表面收益：治理窗口 +0.64pp、全历史 +1.13pp（保留 −3.68% vs 基线 −4.81%）；5d 复核（复权与视界完整）+0.29pp 同向。
- "避掉的回撤"：剔除组尾部显著更深（p10 −17.5% vs 保留组 −15.1%，min −35.1%）。

**敏感性检验（本方案的否决证据）**——同一批行，把分组标签从"记录状态"换成"当前供数重放状态"：

| 状态基准 | 保留 WARM/HOT | 剔除 OVERHEAT | 方案 a 改善 |
|---|---|---|---|
| 记录状态（实时语义） | 450 行/15 日，−4.69% | 561 行/19 日，−5.84% | **+0.64pp** |
| 重放状态（当前供数） | 720 行/24 日，−5.36% | 291 行/10 日，−5.25% | **−0.11pp（消失并轻微反向）** |

12/38 个信号日状态漂移（9 个 OVERHEAT→HOT、1 个 HOT→WARM、1 个 HOT→OVERHEAT、1 个 OVERHEAT→HOT 反向），根因是广度/涨停质量供数修订后重放结果变化。最伤的 05-26~06-01 五个日（日均 −6.5%~−10.2%）记录为 OVERHEAT（方案 a 剔除）、重放为 HOT（方案 a 保留）——**方案 a 的窗口改善主要来自"OVERHEAT 标签恰好盖住最差两周"，标签换版本即消失**。叠加独立观测 ≈2 个的统计力，+0.64~1.13pp 不构成可依赖的预期收益。

### 3.2 方案 b：收紧到 {WARM, HOT, OVERHEAT}（仅剔 OFF）

- 治理窗口与全历史**零行损失、零收益变化**（观测期无 OFF 信号日）；长窗口重放 OFF 频率 0.2%（469 日中 1 日）。
- 实时语义下 OFF 非空集：theme_breakout 执行历史录得 16 个 OFF 信号日（2024-08-30、2025-01、2025-04、2025-11 三段），系当时实时门控判 OFF（现重放全部漂移为 WARM/HOT，一致率 0/16）。即**熊市段/供数缺失段 OFF 会真实出现**，届时 factor_screen 现状会在"门控 0/4 条件、敞口 0~0.25"下继续产新候选。
- 语义收益：消除"门控宣告离场、策略照常供票"的矛盾；下游 hybrid_fusion 自身 {WARM,HOT}，OFF 日剔除对 fusion 供票零影响；实施成本即 §5.2 的执行点补全。
- 该方案的价值不在窗口收益（≈0），在于把**唯一双层重叠收缩的状态（OFF）**收口，且顺带把 NO_DATA/STALE/PENDING_DATA 一并拦截（对齐兄弟策略行为）。

### 3.3 方案 c：维持在场 + gate 敞口缩放——已是现状，勿重复实施

**结论：执行历史回测（path 模式）的敞口已按逐日 gate 缩放（§2.2 代码取证），"方案 c"不是待实施选项而是现状描述。** 本审计以一阶近似量化其效果（每行按信号日敞口缩放收益贡献，镜像引擎入场缩放语义、忽略槽位竞争）：

| 口径 | 治理窗口 | 全历史 |
|---|---|---|
| 未缩放（基线） | −5.33% | −4.81% |
| 敞口缩放贡献（平均敞口 0.80 / 0.78） | **−4.29%** | −3.97% |
| a+c 叠加（WARM/HOT 且缩放） | −3.40% | −2.83% |

- 敞口层在本窗口只提供 ~20% 的收缩（平均敞口 0.8），因为门控自己读数强——**"有敞口机制"与"敞口机制在该窗口有保护力"是两回事**。
- **双重收缩的判定**：a+c 叠加（−3.40%）优于 c 单独（−4.29%），因为两层作用于不同状态集合（信号闸门砍 OVERHEAT=敞口 1.0 的日子，敞口层压 WARM=敞口 0.25~0.5 的日子）——互补而非重复。唯一真正重叠的是 OFF（信号停 + 敞口≈0），即方案 b 的收口对象；对 OVERHEAT 而言信号闸门是唯一收缩手段，不存在"再收紧就是双重收缩"的问题。
- 附带发现：官方回测的逐日敞口序列 **100% 来自重放**（三张持久化表不存在，candidate_history 证据缺 exposure 字段未形成持久化点）——如 2026-05-26~06-01 实时门控为 OVERHEAT（敞口应 1.0），回测重放为 HOT 用 0.75。官方 path 回测的敞口既非实时值也无持久化锚点（发现 G-1）。

### 3.4 方案 d（补充模拟）：OVERHEAT 仅保留 rank≤10

模拟保留 640 行/34 日，池化 −5.19%（+0.14pp）——无意义。且 rank 分层证据与既有诊断规则**方向相反**：

| 治理窗口 20d mean | rank 1-10 | rank 11-30 |
|---|---|---|
| WARM | −5.76% (n=20) | −3.15% (n=40) |
| HOT | −7.12% (n=130) | −3.63% (n=260) |
| OVERHEAT | **−6.36%** (n=190) | **−5.57%** (n=371) |

`livermore_candidate_history_service.py:3950` 的"OVERHEAT 下 rank>10 多因子候选降权观察、优先复核仅覆盖前 10"在本窗口是**反向的**（头部更差；OVERHEAT 内 rank1-5 −6.43%、6-10 −6.29% vs 11-20 −4.36%）。样本不足以推翻该规则，但足以说明其经验依据待复验（发现 M-3）。

### 3.5 统计力披露（诚实声明）

- 治理窗口 34 个信号日跨约 36 个交易日，20d 持有期完全重叠，**不重叠独立观测 ≈ 2 个**；全历史 38 日跨 58 个交易日 ≈ 3 个。
- 分状态更弱：OVERHEAT 19 日全部集中在 04-30~06-22 单一下跌区制，WARM 治理窗口内仅 2 日。
- 状态标签本身 12/38 不可复现（§3.1）。
- 因此本报告所有 pp 级差异只能作方向参考；**任何以"改善收益"为由的门控收紧（方案 a/d）都没有统计基础**，方案 b 因不依赖收益证据（语义修正）不受此限。

---

## 4. 与其他策略的一致性论证：为什么 uptrend 收 WARM/HOT，而 factor_screen 本就该弱化状态门控

**uptrend 族（含 exp3b/exp3c、hybrid_fusion）选择 {WARM,HOT} 的机制**：这些是**时机策略**——信号本体是"突破/放量/强收盘"形态，其有效性依赖市场处于趋势扩张段。OVERHEAT（四腿全绿）意味着突破形态大概率是拥挤顶部的追高（Livermore 原则：不在极端一致的读数上追新仓），OFF 意味着形态失效环境。状态门控在这里是**信号语义的组成部分**：同一根 K 线在 HOT 是信号、在 OVERHEAT 不是。mean_reversion 只在 WARM 同理反向：超跌反弹需要"未走强也未关闸"的中间态。

**factor_screen 是横截面策略，信号无时机含义**：它对快照内全部股票做 9 因子排名，输出"当下基本面性价比最高的 30 只"——名单在快照间（3~7 天）完全不变，与当日市场状态零耦合（这正是 `factor_screen_candidates.py:46` 显式解耦的设计意图）。对它施加状态门控，剔除的不是"坏信号"而是"坏日子里的重复台账行"：OVERHEAT 日被拦的那批票，次日转 HOT 又原样放行。**"哪天开仓、开多大"对横截面策略而言本来就是仓位层（敞口闸门+risk_budget sizing）的职责，而非信号层**。这也是本次模拟的结构性解释：方案 a 砍信号行的效果（+0.64pp，不稳健）远弱于敞口连续缩放（c，−4.29%）与两层叠加（−3.40%）。

**因此机制上的正确分工是：factor_screen 保持弱状态门控（仅剔离场态 OFF 及非活跃态）+ 依赖仓位敞口层——即方案 b + 现状 c。** 与家族的一致性不体现在集合相同，而体现在"时机策略用状态闸信号、横截面策略用状态闸仓位"的分层一致。

**但必须指出敞口层当前的结构缺陷（beta 错配，本窗口负 alpha 的真正机制）**：门控读 CSI300（大盘指数趋势 2 腿+涨停质量腿），而 factor_screen 持仓是中小盘等权（蓝本 §4.3：fail 组市值中位 58 亿）。2026-04~06"指数平、个股普跌"时，门控读数 HOT/OVERHEAT（敞口 0.75~1.0）系统性高估了该组合的安全度——**门控测的是指数 beta，组合暴露的是等权小盘 beta**。这个错配不能靠收紧 active_states 修复（方案 a 敏感性已证明），治本方向是敞口信号源改造（广度腿加权/等权指数腿，或 factor_screen 专属的敞口乘数），属于门控本体的 P2 议题（§5.4）。

---

## 5. 建议

### 5.1 明确推荐

| 优先级 | 决定 | 理由 |
|---|---|---|
| **P1 采纳** | **方案 b**：`factor_screen_active_states` 收紧为 `{WARM, HOT, OVERHEAT}`，并补执行点使其真正生效（含拦截 NO_DATA/STALE/PENDING_DATA） | 语义收口（消除 OFF 双层矛盾）；观测期收益影响≈0（如实定位，不宣称收益修复）；与横截面策略"状态闸仓位不闸信号"的机制分工一致 |
| **P1 前置** | 市场状态/敞口持久化治理（发现 G-1）：落地 `livermore_gate_history`（tasks 层写入，`gate_exposure_series.py:20` 白名单已预留表名），回测与快照验证切 persisted 优先 | 12/38 日漂移、theme_breakout OFF 0/16、stock_candidate 41% 漂移——**不先锚定标签，任何门控变更的回测验证与黄金样本都不可信** |
| 不采纳 | 方案 a（WARM/HOT） | 改善不稳健（重放标签下归零）、无统计力、砍 ~32% 交易日与低频性格冲突；列 P2 复验 |
| 无需实施 | 方案 c | 已是官方回测现状；需要的是语义披露而非代码变更（页面/文档明示"候选输出≠满仓建议，仓位由 gate 敞口层决定"） |
| 不采纳 | 方案 d（OVERHEAT 仅 top10） | +0.14pp 无意义；rank 证据与既有诊断规则反向，先复验规则本身 |

### 5.2 方案 b 实施要求（对齐仓库变更纪律；本审计未改任何代码）

1. **POLICY 字段变更**：`strategy_policy.py:151` 集合改为 `frozenset({"WARM","HOT","OVERHEAT"})`。POLICY 是 frozen dataclass 且有快照测试，必须同步 `backend/tests/core_finance/test_strategy_policy.py:38`（等值断言）；`:239` 的 identity 断言（`factor_screen_candidates.ACTIVE_MARKET_STATES is POLICY.factor_screen_active_states`）不变自动通过。
2. **补执行点**：`compute_factor_screen_candidates` 头部增加状态检查，对齐 `mean_reversion_candidates.py:44` 模式（`market_state not in ACTIVE_MARKET_STATES` → 返回空 items + inactive 语义的 coverage_note/block 原因），删除 `factor_screen_candidates.py:46` 的 `_ = market_state` 解耦与 :13 的"所有市场状态都运行"注释。
3. **FORMULA_VERSION**：v3→v4（输出行为变化：OFF/非活跃态返回空候选），黄金样本新增"OFF 日空候选+原因"用例（`backend/tests/core_finance/test_factor_screen_candidates.py`）。
4. **服务层语义**：inactive 型 coverage_note 不得落入 `_is_factor_screen_error_note` 的错误关键词（`market_data_livermore_service.py:4129`，现有关键词含"为空"），避免被误判为数据降级；`_factor_screen_degradation_reasons` 与监控覆盖率消费需区分"门控 inactive"与"数据缺失"——**OFF 日空候选不应触发 factor_screen 覆盖率/新鲜度告警**。
5. **影响面确认**：候选历史/执行历史物化（OFF 日不再落 factor_screen 行，formula_version 自然断代）；hybrid_fusion 供票（自身 {WARM,HOT}，无实际影响）；深度研究·多因子观察池页面（OFF 日显示 inactive 而非错误，页面契约 `docs/page_contracts.md` 相应分区核对）；`equity_shadow_portfolio`（复用宇宙过滤器但不走状态门控，需在影响报告中确认不受牵连）。
6. **验证顺序**：先落 G-1 持久化，再变更门控，用 persisted 状态序列做变更前后重放对齐。

### 5.3 需要更长窗口复验的事项

1. **方案 a 复验（P2）**：前置=状态标签可复现（G-1）+ ≥2 个独立市场区制（当前 OVERHEAT 样本全部来自单一下跌段）+ ≥50 个快照日；复验口径=分状态 20d 相对评分池的增量（剔 beta），而非绝对收益。
2. **门控-持仓 beta 错配治理（P2）**：为中小盘等权类组合评估敞口信号源（等权指数/广度腿加权）或策略级敞口乘数；这是本窗口 −7.2% 等权 beta 的机制性修复方向。
3. **诊断规则复验（P2）**：`OVERHEAT rank>10 降权观察`（`livermore_candidate_history_service.py:3950`）在窗口内方向相反，待样本扩大后复验或降级为中性展示。
4. **OFF 态保护价值**：本时代 OFF 近乎缺席（重放 1/469），其保护价值只能在熊市样本中检验；方案 b 的收益面评估留待彼时，不影响其语义收口定位。
5. **执行历史 pending 回填**（蓝本 L1 延续）：723 行 pending 未回填 20d，分状态官方口径对比长期不可用。

---

## 6. 按严重级别的发现汇总

| 级别 | 编号 | 发现 | 证据 |
|---|---|---|---|
| **High** | G-1 | **市场状态标签系统性不可复现，且官方回测敞口无持久化锚点**：`PERSISTED_EXPOSURE_TABLES` 三表（`livermore_monitor_append`/`livermore_gate_history`/`livermore_gate_supplement`）均不存在，candidate_history 证据缺 exposure 字段，官方回测逐日敞口 100% replayed；factor_screen 信号日记录 vs 重放漂移 12/38，theme_breakout 记录 OFF 日重放一致率 0/16，stock_candidate 漂移 41%（94/231）。影响：一切状态条件化回测、门控变更验证、快照测试的地基 | `gate_exposure_series.py:20`；本报告 §3.1/§3.3；重放脚本比对 |
| Medium | G-2 | factor_screen `active_states` 声明但无执行点（core `_ = market_state`、服务层无条件调用），且 NO_DATA/STALE/PENDING_DATA 亦不拦截；门控字段空转 | `factor_screen_candidates.py:14/46`；`market_data_livermore_service.py:1823` |
| Medium | G-3 | OVERHEAT 语义误读风险：`exposure_by_market_state` 中 OVERHEAT=(1.0,) 满仓、OFF 才是收缩态；蓝本 P1 条目"OFF/OVERHEAT=门控要求空仓/收缩"表述与 POLICY 不符，本报告予以修正——OVERHEAT 收缩的仅是趋势族新入场信号 | `strategy_policy.py:152-161`；`livermore_strategy.py:158/177` |
| Medium | G-4 | 诊断层"OVERHEAT 下 rank>10 降权观察、仅前 10 优先复核"与窗口证据方向相反（OVERHEAT rank1-10 −6.36% vs 11-30 −5.57%；HOT −7.12% vs −3.63%），经验依据待复验 | `livermore_candidate_history_service.py:3872-3955`；§3.4 |
| Low | G-5 | 执行历史 20d 收益冻结未回填延续（1131 行仅 408 行有值、2026-06-10 后全 pending），缺失沿状态极端不均（WARM 0 行）——分状态官方口径对比不可行 | `data_status` 分布；蓝本 L1 延续 |
| Low | G-6 | `factor_screen_candidates.py:13` 注释"所有市场状态都运行"与声明集不含 NO_DATA/STALE/PENDING_DATA 的事实不一致（无执行点时无实际影响，实施方案 b 时一并清理） | 同文件 :13-14 |

**总体健康度**：门控/敞口的**机制设计**（两层分工、per-date 敞口、状态机）自洽且已在官方回测生效；问题集中在**治理层**——门控字段空转（G-2）、状态标签不可复现（G-1）、语义表述漂移（G-3）。按"G-1 持久化 → 方案 b 语义收口"顺序实施后可达"机制与语义一致"状态；收益面的门控优化（方案 a 类）在获得可复现标签与多区制样本前不应启动。

**测试覆盖缺口**：

1. factor_screen 门控行为测试缺失（inactive 状态返回空+原因；现测试文件无任何 market_state 分支用例）；
2. `test_strategy_policy.py` 仅断言集合值，无"active_states 声明必须有执行点"的结构性防护（G-2 类问题无法被测试捕获）；
3. 状态序列重放一致性测试缺失（记录 vs 重放漂移无监控，G-1 落地后应加持久化-重放对账断言）；
4. 官方回测敞口来源断言缺失（persisted/replayed/fallback 比例无监控字段消费）。

---

## 附录 A：38 个信号日明细（20d/5d 为当日候选等权净收益重算值）

| signal_date | 记录状态 | 重放状态 | 重放敞口 | 行数 | 20d 日均 | 5d 日均 | CSI300 20d 前瞻 |
|---|---|---|---|---|---|---|---|
| 2026-04-30 | OVERHEAT | OVERHEAT | 1.00 | 27 | −3.47% | +0.32% | +2.23% |
| 2026-05-06 | OVERHEAT | OVERHEAT | 1.00 | 27 | −3.63% | +0.77% | +1.27% |
| 2026-05-07 | OVERHEAT | OVERHEAT | 1.00 | 27 | −4.12% | −0.86% | +0.09% |
| 2026-05-08 | OVERHEAT | OVERHEAT | 1.00 | 30 | −8.21% | −3.39% | −1.13% |
| 2026-05-11 | OVERHEAT | OVERHEAT | 1.00 | 30 | −10.40% | −4.38% | −4.81% |
| 2026-05-12 | OVERHEAT | OVERHEAT | 1.00 | 30 | −8.12% | −2.52% | −2.96% |
| 2026-05-13 | OVERHEAT | OVERHEAT | 1.00 | 30 | −8.58% | −4.55% | −5.00% |
| 2026-05-14 | OVERHEAT | HOT | 0.75 | 30 | −7.25% | −4.40% | −3.91% |
| 2026-05-15 | OVERHEAT | HOT | 0.75 | 30 | −5.72% | −2.85% | −1.69% |
| 2026-05-18 | HOT | HOT | 0.75 | 30 | −4.56% | −2.72% | +1.20% |
| 2026-05-19 | HOT | HOT | 0.75 | 30 | −6.02% | −3.43% | +0.65% |
| 2026-05-20 | HOT | HOT | 0.75 | 30 | −3.34% | −2.92% | +1.66% |
| 2026-05-21 | HOT | WARM | 0.50 | 30 | −3.45% | −2.43% | +3.31% |
| 2026-05-22 | HOT | HOT | 0.75 | 30 | −3.70% | −3.55% | +4.43% |
| 2026-05-25 | HOT | HOT | 0.75 | 30 | −4.93% | −0.74% | −0.04% |
| 2026-05-26 | OVERHEAT | HOT | 0.75 | 30 | −6.49% | −0.85% | −0.10% |
| 2026-05-27 | OVERHEAT | HOT | 0.75 | 30 | −7.81% | +0.01% | +2.28% |
| 2026-05-28 | OVERHEAT | HOT | 0.75 | 30 | −10.21% | −1.92% | −0.94% |
| 2026-05-29 | OVERHEAT | HOT | 0.75 | 30 | −7.65% | −0.92% | +0.71% |
| 2026-06-01 | OVERHEAT | HOT | 0.75 | 30 | −9.82% | −4.55% | +2.79% |
| 2026-06-02 | HOT | HOT | 0.75 | 30 | −7.93% | −3.50% | +0.90% |
| 2026-06-03 | HOT | HOT | 0.75 | 30 | −7.20% | −3.02% | −2.56% |
| 2026-06-04 | OVERHEAT | HOT | 0.75 | 30 | −5.09% | −2.64% | −1.28% |
| 2026-06-05 | HOT | HOT | 0.75 | 30 | −3.39% | −0.35% | +0.52% |
| 2026-06-08 | WARM | WARM | 0.50 | 30 | −5.42% | +0.40% | +1.67% |
| 2026-06-09 | HOT | HOT | 0.75 | 30 | −4.28% | +0.20% | −0.96% |
| 2026-06-10 | HOT | HOT | 0.75 | 30 | −3.56% | −0.34% | +2.69% |
| 2026-06-11 | WARM | WARM | 0.50 | 30 | −2.62% | −1.55% | +1.24% |
| 2026-06-12 | HOT | HOT | 0.75 | 30 | −5.76% | −2.61% | −1.72% |
| 2026-06-15 | HOT | OVERHEAT | 1.00 | 30 | −4.20% | −3.72% | −1.95% |
| 2026-06-16 | OVERHEAT | HOT | 0.75 | 30 | −0.81% | −3.73% | −2.00% |
| 2026-06-17 | OVERHEAT | OVERHEAT | 1.00 | 30 | +0.32% | −3.71% | −4.72% |
| 2026-06-18 | OVERHEAT | OVERHEAT | 1.00 | 30 | −1.63% | −3.92% | −8.35% |
| 2026-06-22 | OVERHEAT | HOT | 0.75 | 30 | −1.59% | −3.60% | −9.12% |
| 2026-07-08 | WARM | WARM | 0.50 | 30 | +3.77% | +2.92% | −2.05% |
| 2026-07-10 | WARM | WARM | 0.25 | 30 | +4.07% | +2.51% | −1.81% |
| 2026-07-21 | WARM | WARM | 0.25 | 30 | 截断 | −0.13% | 截断 |
| 2026-07-24 | WARM | WARM | 0.25 | 30 | 截断 | +3.67% | 截断 |

## 附录 B：复现要点

- factor_screen 执行历史：`livermore_candidate_execution_history where signal_kind='factor_screen'`（1131 行、38 个 distinct signal_date、129 只股票，逐行含信号日实时 `market_state`）；治理窗口=蓝本同窗（signal_date ≤ 2026-06-22，1011 行/34 日）。
- 状态/敞口序列：`backend.app.core_finance.gate_exposure_series.load_gate_exposure_by_date`（与官方回测同函数；本期输入下 100% replayed）；长窗口频率取 2024-09-02~2026-08-11 共 469 个有效交易日。
- 收益重算：§1.2 口径；复权因子去重 `row_number() over (partition by stock_code, trade_date order by run_id desc, source_version desc)=1`（同日多 run 混用会产生数量级伪收益，复现时必做）。
- 方案 c 的资本缩放为一阶近似：`mean(exposure(signal_date) × r20)`，镜像 `portfolio_backtest` 入场缩放语义，忽略槽位竞争与持仓期敞口再平衡（引擎不做后者）。
- 所有临时脚本（`_tmp_gate_0*.py`）已于报告落稿后删除；本报告为唯一产物。
