# `/stock-analysis` D6a / D6b 受控实施审计

- 日期：2026-08-22
- 页面：`/stock-analysis`
- 页面边界：`observational_only`、`formal_use_allowed=false`
- 本轮范围：D6a controlled v46 、D6b dry-run / materialize / promote / rollback 的代码与临时库闭环，以及 live 库只读不变验收

## 1. 当前结论

1. D6a 的 controlled v46 已存在，但默认启动链没有自动注册它；普通启动仍停在 v45。
2. D6b 的 `dry-run` / `materialize` / `promote` / `rollback` 四个入口已实现；临时 DuckDB 上已验证物化、唯一 active 切换、有/无前驱回退、幂等重放、事务失败回滚与 receipt 链接。
3. 这轮没有把前端、API、旧 `as_produced` 历史闭环、或 PMI 正式信用脉冲纳入验收。
4. `data/moss.duckdb` 仍是 v45，未发现任何 `stock_analysis_current_rule_%` D6 表。
5. 本轮结论是 **受控代码闭环 PASS，生产数据提升 NO-GO**。真实 approved calendar、历史 source-availability attestation、完整 PIT cohort 和外部可信审批尚未具备，因此没有伪造 active 生产批次。

## 2. 代码证据

| 证据 | 位置 | 含义 |
| --- | --- | --- |
| controlled v46 只走显式入口 | `backend/app/repositories/duckdb_migrations.py`、`backend/app/schema_registry/duckdb/controlled/45_stock_analysis_current_rule_cohort.sql`、`tests/test_stock_analysis_current_rule_cohort_schema_controlled.py` | 默认迁移链只到 v45；v46 需要受控入口，且测试覆盖了“默认不注册 / 受控幂等 / 缺前置 ledger 失败闭合” |
| D6b 受控写链 | `backend/app/tasks/stock_analysis_current_rule_cohort_materialize.py` | 模块文档明确不注册到 task broker；写入口要求 `allow_write=True`、writer lock、dry-run receipt、approval hash、pre-write backup |
| D6b 临时库验收 | `tests/test_stock_analysis_current_rule_cohort_materialize.py` | 验证 20/100 门槛、严格开市日覆盖、来源 tuple/PIT、串库阻断、备份、receipt path+hash、唯一 active、两类回退和生命周期后重放拒绝 |
| live 库状态 | `data/moss.duckdb` | 只读核对显示 max migration = 45，D6 表计数为 0 |

## 3. 本轮不纳入

- 不改前端页面。
- 不改后端 API / service 读路径。
- 不把旧 `as_produced` 当成 current-rule certified cohort。
- 不推进 PMI 正式信用脉冲的生产认证。
- 不把真实生产库写入当作已完成。

## 4. 验证结果

- 只读查询 `data/moss.duckdb`：`max(version) = 45`，`stock_analysis_current_rule_%` 表数为 `0`。
- D6a + D6b 定向：`34 passed`。
- 扩展回归（calendar receipt、zero-signal certificate、matched baseline、current-rule dry-run、gap ledger、schema consistency、D6a、D6b）：`116 passed`。
- Ruff 与 `py_compile`：PASS。
- 独立代码复审：PASS，无剩余 BLOCK/HIGH。

## 5. 已知阻断

1. Approval artifact 是 canonical hash 完整性合同，还不是外部数字签名或可信审批服务；上生产前必须补齐身份真实性边界。
2. 真实历史数据目前没有同时满足 approved calendar、source availability、每候选 20 个可用对照、T5/T20 及 20/100 门槛的 certified bundle，所以 production promotion 继续 fail closed。
3. API/页面还没有读 active certified cohort；因此页面闭环仍需 M1-C，且仍必须保持 `observational_only`。
4. PMI 可沿用已有序列和 PIT 证据，但正式信用脉冲的公式、GDP/vintage 与 1M/3M 窗口仍属 M2，本轮没有将代理指标冒充为正式信用脉冲。

## 6. 结论

- `controlled schema + task state machine`：PASS。
- `live schema/data promotion`：NO-GO，本轮未执行。
- `page closed`：未完成，待 M1-C 读路径与页面合同验收。
- `formal credit impulse`：未完成，待 M2 指标合同。
