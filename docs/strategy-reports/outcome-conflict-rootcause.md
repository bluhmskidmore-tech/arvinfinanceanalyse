# `stored_target_conflict` 根因调查

- 调查日期：2026-08-12
- 评估截止日：2026-08-12
- 数据源：`data/moss.duckdb`，全程 `read_only=True`
- 代码入口：`backend/app/tasks/livermore_candidate_outcome_maturity.py`
- 范围：只读调查与修复方案；未修改生产代码或 DuckDB

## 执行结论

1. `stored_target_conflict` 比较的是**目标交易日期**，不是目标价。具体是候选历史表的 `forward_trade_date_{1d|5d|10d|20d}`，与回补任务从当前 `choice_stock_daily_observation` 中按个股“第 N 个有效 bar”重排出的日期比较。
2. 当前库共有 **125 个物理 horizon 冲突单元，落在 123 个物理候选行**。任务最终 `issues` 只显示 **105 个唯一字符串**，因为 issue 不含 `rowid/signal_kind`，且返回前执行了 `sorted(set(issues))`，20 个重复候选身份被折叠。
3. 冲突由两类根因组成：
   - **119 个单元：历史行情快照后续被补齐/重建。** 旧回补在稀疏日历上把 2026-07-21 当成第 5/20 个 bar；当前 2026-08-11 行情重建后，2026-07-15 才是第 5/20 个 bar。
   - **6 个单元：停复牌状态口径。** 当前白名单不包含“复牌”，导致可交易复牌日也被排除；603268.SH 四个单元、688260.SH 两个重复单元均可由此解释。
4. 不是 2026-06-16 附近的长假或市场性停牌潮。300308.SZ 当前日期链显示 7 月 13—17 日及 7 月 20—21 日均正常交易；统一四日偏移来自历史行情补齐。
5. `livermore_candidate_execution_history` 不是冲突来源，也不应作为仲裁权威。抽样的 2026-06-16 执行历史只回建到 2026-06-26，`exit_date_20d` 仍为空；且执行口径包含 next-open、可卖性顺延，与候选 forward-close 口径不同。
6. 推荐采用“**当前修订行情为分析主值，旧值完整留痕**”的仲裁规则，但应先统一交易状态语义、补齐复权因子，再原子替换 horizon 三元组。若业务要保留“当时已知”口径，则必须建设双时态行情快照；当前可变表无法可靠重放旧日历。

## 1. 冲突判定的精确语义

### 1.1 重算目标

任务对 `choice_stock_daily_observation` 做以下处理：

1. 只取 `snapshot_as_of_date < trade_date <= evaluation_as_of_date`。
2. 同一 `stock_code + trade_date` 按 `rowid desc` 只取最新修订。
3. `close_value` 必须有限且大于 0。
4. 若表含 `tradestatus`，状态必须属于：
   - `trading`
   - `交易`
   - `正常交易`
5. 按个股日期升序编号；第 1/5/10/20 个有效 bar 分别是各 horizon 的 `computed_target`。

关键代码：

- `backend/app/tasks/livermore_candidate_outcome_maturity.py:241-320`
- `backend/app/tasks/livermore_candidate_outcome_maturity.py:605-625`

### 1.2 触发条件

对每个 horizon：

```text
stored_target_date = livermore_candidate_history.forward_trade_date_{horizon}
computed_target_date = 当前有效行情序列中的第 N 个日期

若 stored_target_date 非空
且 computed_target_date 存在
且两者不相等
=> stored_target_conflict
```

它**不比较**：

- 目标收盘价；
- `return_{horizon}`；
- `return_{horizon}_adj`；
- 候选历史与执行历史的目标日期。

若冲突：

- `target_date` 和 `target_close` 留空；
- 不覆盖 stored date；
- 不重算该 horizon 的 raw/adjusted return；
- 不加载该冲突目标日的复权因子；
- 市场已成熟时，该 horizon 被分类为 `matured_missing_bar`。

这不是整行 `blocked_row`：冲突只进入 `issues`，同一行其他 horizon 仍可更新。因此“整行被跳过”并不精确；真正被保守跳过的是冲突 horizon 的目标与收益回补。

### 1.3 对读路径的放大效应

服务读路径会把 `target_observation_verified=false` 的 horizon 的以下三个字段全部置空：

- `forward_trade_date_{horizon}`
- `return_{horizon}`
- `return_{horizon}_adj`

见 `backend/app/services/livermore_candidate_history_service.py:1246-1275`。

回测窗口又规定：某 snapshot 只要有任一候选行 `data_status=pending`，整日就不进入 completed statistics，见同文件 `1845-1902`。因此单个 horizon 冲突会被放大为行级乃至日期级遮挡。

## 2. 真实库逐案证据

### 2.1 2026-06-16 六只股票

六只股票都来自候选 run：

`livermore_candidate_history:2026-06-16:6a59c52945e9`

当前重算目标行情都来自：

`choice_stock_materialize:2026-08-11:3b4e226f523e`

| 股票 | 选择价 | 存储目标/当前该日收盘 | 存储 raw / adj | 当前第 20 bar/收盘 | 当前 raw / adj |
|---|---:|---|---:|---|---:|
| 002428.SZ 云南锗业 | 101.20 | 2026-07-21 / 73.98 | -26.8972% / -26.8903% | 2026-07-15 / 87.83 | -13.2115% / 缺因子 |
| 300308.SZ 中际旭创 | 1248.09 | 2026-07-21 / 1136.55 | -8.9369% / -8.9369% | 2026-07-15 / 1169.31 | -6.3120% / 缺因子 |
| 600007.SH 中国国贸 | 18.70 | 2026-07-21 / 18.93 | +1.2299% / +7.2322% | 2026-07-15 / 20.23 | +8.1818% / 缺因子 |
| 600050.SH 中国联通 | 4.37 | 2026-07-21 / 4.39 | +0.4577% / +1.6907% | 2026-07-15 / 4.27 | -2.2883% / 缺因子 |
| 601766.SH 中国中车 | 5.72 | 2026-07-21 / 5.99 | +4.7203% / +4.7203% | 2026-07-15 / 5.60 | -2.0979% / 缺因子 |
| 688530.SH 欧莱新材 | 63.16 | 2026-07-21 / 56.20 | -11.0196% / -11.0196% | 2026-07-15 / 68.41 | +8.3122% / 缺因子 |

存储 raw return 均能由“当前 7 月 21 日收盘 / selection_close - 1”复算出来，说明旧的 target/date/return 三元组内部一致，不是随机写坏。冲突在于：按当前完整日历，7 月 21 日已是第 24 个有效 bar，而非第 20 个。

这六只的执行历史均为：

- `entry_date=2026-06-17`
- `exit_date_20d=NULL`
- `data_status=pending`
- run 截止到 `2026-06-26`

所以不存在“执行历史另有正确 target，与候选历史互相覆盖”的证据。

### 2.2 300308.SZ 的历史审计证据

候选行内 `signal_evidence_json.outcome_maturity_audit` 保留了旧回补事件：

| evaluation date | 当时市场/个股有效 bar | 当时 20d 状态 | 当时目标 | 目标行情 run |
|---|---:|---|---|---|
| 2026-07-12 | 15 / 15 | natural_pending | NULL | NULL |
| 2026-07-21 | 20 / 20 | complete | 2026-07-21 | `choice_stock_materialize:2026-07-21:d41d1732722c` |

2026-07-21 的事件明确写入了：

- `forward_trade_date_20d`
- `return_20d`
- `return_20d_adj`

而当前 2026-08-11 行情重建后，6 月 16 日至 7 月 21 日已有 24 个有效 bar。这直接证明：**旧值是旧行情快照上的正确结果；当前冲突由历史行情补齐后日历排名改变造成。**

2026-07-08 的 603268.SH 审计给出同类旁证：

- 2026-07-21：只看到 5 个有效 bar，第 5 个为 2026-07-21；
- 2026-07-24：已看到 12 个有效 bar。

三个自然日内有效 bar 数从 5 跳到 12，不可能是市场自然新增，必然包含历史日期补入。

### 2.3 603268.SH 两个 snapshot

| snapshot | horizon | 存储目标 / raw | 当前重算目标 / raw |
|---|---|---|---|
| 2026-04-07 | 10d | 2026-04-22 / +17.5291% | 2026-04-23 / +18.5358% |
| 2026-04-07 | 20d | 2026-05-11 / +34.3594% | 2026-05-12 / +33.1115% |
| 2026-04-08 | 10d | 2026-04-23 / +13.6567% | 2026-04-24 / +16.7916% |
| 2026-04-08 | 20d | 2026-05-12 / +27.6324% | 2026-05-13 / +31.6847% |

当前行情状态：

- 2026-04-17：`停牌一天`，close=121.22，任务排除；
- 2026-04-20：`复牌`，close=133.34，任务也排除。

存储日期恰好对应“排除 4 月 17 日停牌、计入 4 月 20 日复牌”的链；当前任务把两天都排除，因此目标整体顺延一个交易日。

同类情况还出现在 2026-06-08 的 688260.SH 两个重复候选行：

- 存储 20d：2026-07-10
- 当前重算：2026-07-13
- 2026-06-26、06-29、06-30 为`连续停牌`
- 2026-07-01 为`复牌`，但当前白名单仍排除

因此停牌日排除是合理的；**复牌日排除不合理**，是可直接修正的状态语义缺口。

## 3. 冲突影响量化

### 3.1 物理单元与 issue 分布

| snapshot | horizon | 存储日期 → 当前日期 | 物理单元 |
|---|---|---|---:|
| 2026-04-07 | 10d | 04-22 → 04-23 | 1 |
| 2026-04-07 | 20d | 05-11 → 05-12 | 1 |
| 2026-04-08 | 10d | 04-23 → 04-24 | 1 |
| 2026-04-08 | 20d | 05-12 → 05-13 | 1 |
| 2026-06-08 | 20d | 07-10 → 07-13 | 2 |
| 2026-06-16 | 20d | 07-21 → 07-15 | 35 |
| 2026-07-08 | 5d | 07-21 → 07-15 | 84 |
| **合计** |  |  | **125** |

按 horizon：

- 5d：84
- 10d：2
- 20d：39

按物理行/issue：

- 物理候选行：123
- 物理 horizon 冲突单元：125
- 对外唯一 issue 字符串：105
- 因 issue 去重被折叠：20

### 3.2 字段影响

- 与当前日历冲突的存储日期字段：125
- 125 个冲突 horizon 的 raw return：全部已有值
- 因冲突未能填充的 adjusted return：86
  - 2026-06-08 20d：2
  - 2026-07-08 5d：84
- 读路径会把每个冲突 horizon 的日期/raw/adj 三个字段一起遮蔽：125 × 3 = **375 个对外值**

不能只覆盖日期：日期改变后，raw、adjusted、`ex_div_in_window`、`data_status` 都可能改变。

### 3.3 策略评估窗口遮挡

冲突涉及 5 个 snapshot 日。因为日期级规则是“任一行 pending 则整日不进入 completed statistics”，这些日期上的候选行总量为：

| snapshot | 全日候选行 | 冲突物理行 | 全日 pending | 非冲突 pending |
|---|---:|---:|---:|---:|
| 2026-04-07 | 61 | 1 | 12 | 11 |
| 2026-04-08 | 90 | 1 | 11 | 10 |
| 2026-06-08 | 100 | 2 | 100 | 98 |
| 2026-06-16 | 50 | 35 | 50 | 15 |
| 2026-07-08 | 107 | 84 | 107 | 23 |

以候选历史最新 snapshot 2026-07-24 为锚：

- 近 30 日：遮挡 2026-07-08，107 行；
- 近 60/90 日：遮挡 2026-06-08、06-16、07-08，共 257 行；
- 默认 180 日：五日全部落入，共 408 行。

但需要修正背景中的一个推断：**冲突不是这些日期唯一的阻塞。** 每个冲突日期都还有非冲突 pending 行；只修 125 个 conflict，不会立即让任何一个 snapshot 日恢复 completed。空 `tradestatus` 与复权因子缺口必须一起处理。

20d 的 172 个 `natural_pending` 是正常未成熟窗口：

- 2026-07-21：96 行
- 2026-07-24：76 行

它们不属于本次根因。

## 4. `matured_missing_bar=1018` 的性质

20d 视角 1018 行可拆为：

| 类型 | 行数 | 结论 |
|---|---:|---|
| 空状态过滤造成的假缺失 | 976 | 有至少 20 个正价 bar，但 `tradestatus=''`，任务全部排除 |
| `stored_target_conflict` | 39 | 有 20 个有效 bar，但日期不一致后主动置为不可用 |
| 当前行情历史回退/丢失 | 2 | 当前 bar 不足，但历史行已有 target 和 raw return，不能解释为真实无行情 |
| 可能真实稀疏 | 1 | 600070.SH 仅 14 个后续 bar、无 stored target，需证券主数据确认退市/长期停牌 |
| **合计** | **1018** |  |

976 个空状态行中：

- 971 行当前有效 bar 数为 0；
- 全部都有至少 20 个“正价但空状态”的 bar；
- 937 行历史上已存 20d target 和 raw return。

这说明 `matured_missing_bar` 在当前实现中主要不是“缺行情”，而是“状态字段缺失被当成不可交易”。

对 2025-12-05 至 2026-08-12 的全表空状态正价记录检查：

- 空状态且正 close：218,227
- 同时 volume、amount 为正：217,883
- volume、amount 均为 0：344

99.8% 以上空状态正价记录有真实成交证据。安全的回退不应把所有空状态一刀切为无效；应区分“空状态但有成交”与“空状态且无成交”。

另外两条当前历史回退证据：

- 600608.SH：当前仅 14 个后续 bar，但历史已存 2025-12-08 target 和收益；
- 600599.SH：当前无后续 bar，但历史已存 2026-04-27 target 和收益。

它们更像当前 observation 重建后的历史覆盖退化，不是真实市场无 bar。

### 4.1 `raw_matured_adjustment_missing=1460`

这是独立的复权因子覆盖问题：

- 仅目标日因子缺失：1,349
- signal 与目标日因子都缺失：111
- 合计：1,460

六月样本的新目标 2026-07-15 均缺目标日因子，因此即使立即接受新 target，也只能得到 raw return，不能安全保留旧日期对应的 adjusted return。

## 5. 独立交叉验证

未调用任务的更新入口，而是直接从行情表取 300308.SZ 最新修订记录，按日期手工编号。2026-06-16 后的有效日期链为：

```text
 1  06-17    2  06-18    3  06-22    4  06-23    5  06-24
 6  06-25    7  06-26    8  06-29    9  06-30   10  07-01
11  07-02   12  07-03   13  07-06   14  07-07   15  07-08
16  07-09   17  07-10   18  07-13   19  07-14   20  07-15
21  07-16   22  07-17   23  07-20   24  07-21
```

- 第 20 个 bar：2026-07-15，close=1169.31
- 手工 raw return：`1169.31 / 1248.09 - 1 = -6.3120%`
- 存储目标：2026-07-21，close=1136.55
- 存储 raw return：`1136.55 / 1248.09 - 1 = -8.9369%`

手工链与任务当前重算一致；候选行旧审计又独立证明 2026-07-21 当时只看到 20 个 bar。两种方法共同确认“历史行情快照补齐导致 target 排名漂移”。

## 6. 推荐仲裁规则

### 6.1 推荐主规则

采用“**revision-current canonical + point-in-time audit**”：

1. 当前经质量门校验的最新行情序列作为分析主值；
2. 旧 tuple 不丢弃，完整写入 `signal_evidence_json.outcome_maturity_audit`；
3. 若业务另需“当时已知”结果，从 audit/bitemporal 快照读取，不与当前修订主值混用。

理由：

- forward 5/10/20d 的业务含义是实际第 N 个可交易 bar；
- 当前读路径已经用当前 observation 重验 stored target；
- 继续保留旧 target 为主值，会把当前日历的第 24 个 bar 标成 20d；
- 但旧值在旧数据快照上并非错误，必须保留以支持可追溯性。

### 6.2 仲裁前先统一交易状态

建议把任务 SQL 与服务/仓储统一到共享交易状态规范，避免任务内硬编码：

1. 明确有效：
   - `trading`
   - `交易`
   - `正常交易`
   - `复牌`
2. 明确无效：
   - `停牌一天`
   - `连续停牌`
   - 其他明确停牌状态
3. 空/未知状态：
   - close、OHLC 有限且为正；
   - 且 `volume > 0 OR amount > 0`；
   - 则标记为 `inferred_trading` 并计入；
   - 无成交证据则不计入，保留 `status_unknown` issue。

当前共享词表位于 `backend/app/core_finance/field_normalization.py:38-48`，而 outcome task 又复制了一份 SQL 白名单；实施时应消除双口径。

修正后：

- 603268.SH、688260.SH 的状态类冲突应自然消失；
- 976 个假 `matured_missing_bar` 应大幅下降；
- 不需要用覆盖 stored target 的方式掩盖状态语义错误。

### 6.3 剩余日期冲突的决策

状态归一化后仍不一致时：

1. 为旧、新序列生成 `calendar_signature`：
   - 有序 `(trade_date, status_resolution, observation source/run)`；
   - 至少覆盖到该 horizon；
   - 记录目标 close 与复权因子版本。
2. 当前序列必须通过：
   - stock/date 最新修订唯一；
   - 第 N bar 可复算；
   - close 有限且为正；
   - 市场日期连续性检查；
   - 来源 run/source_version 不早于旧 audit。
3. 通过则 current wins；否则继续保守跳过，输出结构化 unresolved issue。

本次预计分类：

- 119 个行情修订冲突：current wins；
- 6 个状态语义冲突：修正状态后 stored 与 computed 应相等，无需覆盖。

### 6.4 原子更新要求

current wins 时，必须按 horizon 原子处理：

- 旧 `forward_trade_date`
- 旧 raw return
- 旧 adjusted return
- 新 `forward_trade_date`
- 新目标 close
- 新 raw return
- 新 adjusted return
- 旧/新 observation lineage
- 旧/新 factor lineage
- 仲裁原因与 calendar signature

生产列更新至少包括：

- `forward_trade_date_{horizon}`
- `return_{horizon}`
- `return_{horizon}_adj`
- `ex_div_in_window`
- `data_status`
- `signal_evidence_json`

禁止在日期变化后保留旧 adjusted return。若新目标因子缺失：

- 写入新日期与新 raw；
- `return_*_adj` 置空；
- 状态明确为 `raw_matured_adjustment_missing`；
- 或更保守地先完成因子回补，再一次性切换。

为尽快恢复近月评估，推荐顺序是：**状态归一化 → 复权因子补齐 → dry-run 仲裁 → 原子覆盖。**

### 6.5 issue 与审计格式

现有扁平 issue 丢失物理行信息。建议至少记录：

```json
{
  "type": "stored_target_conflict",
  "candidate_rowid": 6984,
  "snapshot": "2026-06-16",
  "stock": "300308.SZ",
  "horizon": "20d",
  "stored": {"date": "2026-07-21", "raw": -0.0893685552},
  "computed": {"date": "2026-07-15", "raw": -0.0631204480},
  "decision": "current_revision_wins",
  "reason": "historical_calendar_backfill",
  "old_lineage": {},
  "new_lineage": {}
}
```

可继续使用现有 `signal_evidence_json`，不要求立即改表结构。

## 7. 实施验证要点

建议增加的定向测试：

1. 旧回补只看到稀疏日历，后续补入历史 bar，current-wins 并保留旧 tuple；
2. `停牌一天`/`连续停牌`不计入，`复牌`计入；
3. 空状态 + 正成交计入，空状态 + 零成交不计入；
4. target 改变时 raw/adj 原子重算，不沿用旧 adj；
5. 新目标因子缺失时落为 `raw_matured_adjustment_missing`；
6. 重复候选身份按物理 `rowid` 审计，不被 issue 字符串去重吞掉；
7. 服务层确认 conflict 修复后不再遮蔽对应 horizon；
8. 日期级窗口验证需同时处理非 conflict pending，不能只断言 conflict 清零。

验收指标建议：

- `stored_target_conflict` 125 个物理单元全部被分类；
- 6 个状态类冲突在归一化后消失；
- 119 个 revision conflict 有 old/new tuple 和 lineage；
- 86 个 adjusted-return 缺口在因子补齐后闭合；
- `matured_missing_bar` 不再把 976 个空状态有成交 bar 误报为缺行情；
- 对 600070.SH、600608.SH、600599.SH 保留单独数据质量 issue。

## 8. 限制与剩余风险

1. `user-moss-lineage-evidence` 与 `user-moss-data-catalog` MCP 在本次调查中均处于 live discovery error；本报告使用了本地只读库、候选行内嵌 audit 和代码作为替代证据。
2. 当前 observation 是可变的最新快照，没有保留 2026-07-21 的完整逐日旧序列；可以证明当时只有 20 个 bar，但不能从当前库精确恢复当时缺失的是哪四天。
3. 复权因子缺口仍会阻止 adjusted-close 口径完成；只仲裁 target 不足以恢复 completed statistics。
4. 若未来要求严格 point-in-time 回测，应保存 observation/factor 的双时态快照或可重放版本，不能依赖可变表加单个 target 残值。

