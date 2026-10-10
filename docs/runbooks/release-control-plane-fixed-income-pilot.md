# MOSS 统一发布控制面：固定收益受控试点与回滚演练 Runbook

执行状态：**BLOCKED — 本文档不授权当前试点、回滚或任何生产写入**。

本文档只记录在 owner、工单、备份、停写和审批闭合后可执行的受控演练模板。仓库内非生产机械演练已经通过，但它不替代生产批准，不把隔离演练写成正式授权，也不把 `PENDING` 字段伪装成已完成事实。

本页只承接已确认的控制面入口、现有门禁和回执形状，范围与 `[PRD：MOSS 统一发布控制面](../prd-release-control-plane.md)`、[MOSS 统一发布控制面执行方案](../release-control-plane-execution-plan.md) 一致。当前仍待 owner 冻结的内容，统一标记为 `PENDING`。

## 1. 适用范围

本 runbook 只覆盖 `duckdb-main` whole-bundle 的固定收益受控试点、受控回切和回滚演练。它不覆盖认证、RBAC、其他数据库 schema 重构、无关业务域的发布，亦不允许把单一逻辑 lane 当成可独立物理切换的整库。

试点分两类路径。

第一类是同一停写窗口内、writer 尚未恢复、且其他域没有前进时的 `sealed_bundle_reactivate` 回切。第二类是 writer 已恢复或其他域已经有新写入后的 `forward_rebuild` 新 rollback bundle。两类路径不能混写，后者不能直接指向旧整库文件。

## 2. 当前状态

| 项目 | 状态 |
| --- | --- |
| 生产授权 | `BLOCKED` |
| 合成隔离机械演练 | `PASSED`（仅证明 whole-bundle promote/rollback、负向探针和回执复验） |
| 生产拓扑 | `PENDING` |
| `duckdb-main` 绝对路径 | `PENDING` |
| 维护窗口 | `PENDING` |
| RTO / RPO | `PENDING` |
| 观察窗口 | `PENDING` |
| 回滚策略 | `PENDING`（必须区分同窗回切与新 rollback bundle） |
| 后端 / 前端兼容构建 | `PENDING` |

已确认但仅作为入口而非授权的 CLI / 脚本如下。

| 入口 | 作用 |
| --- | --- |
| `scripts/release_control.py prepare` | 冻结 release manifest |
| `scripts/release_control.py validate` | 绑定验证回执 |
| `scripts/release_control.py approve-record` | 记录结构化审批回执 |
| `scripts/release_control.py promote` | 提升已冻结 release |
| `scripts/release_control.py rollback` | 受控回滚，支持 `sealed_bundle_reactivate` 与 `forward_rebuild` |
| `scripts/release_control.py show` | 查询 release 状态 |
| `scripts/wp7_fixed_income_pilot_preflight.py` | 只读检查结构化交接包；字段齐全也不授权生产，固定保持 `release_eligible=false`、`authorizes_pilot=false` 与 `production_writes=false` |
| `scripts/wp7_release_rehearsal.py run` | 只在新建绝对路径和临时 SQLite 中执行合成 whole-bundle promote/rollback；固定不可生产放行 |
| `scripts/wp7_release_rehearsal.py verify` | 复验演练回执自哈希、固定 artifact 路径和文件 checksum |
| `scripts/backend_release_suite.py --mcp-profile fast` | 既有后端发布保护面，作为兼容构建 / contract 证据的一部分 |
| `scripts/check_average_balance_business_owner_approval.py --require-captured` | 既有审批门禁，作为五态审批证据的一部分 |

结构化预检按下面的顺序使用。先打印机器模板，由 owner 在受控工单制品中逐项填写；再把完整 JSON 交给预检器。模板态退出码为 `4`，字段阻断为 `2`，结构完整但仍待 owner 执行为 `3`，输入或输出无效为 `1`。该入口故意没有返回 `0` 的生产继续态，调用方必须读取 JSON 状态，不能仅凭 shell 成功码串联后续动作。

```powershell
.\.venv\Scripts\python.exe scripts/wp7_fixed_income_pilot_preflight.py --print-template
.\.venv\Scripts\python.exe scripts/wp7_fixed_income_pilot_preflight.py --packet <handoff-packet.json> --output output/wp7-fixed-income-pilot-preflight.json
```

`--print-template` 只打印 JSON，不创建文件。`--output` 只允许在当前仓库既有的 `output/` 或 `.tmp/` 中独占新建 `.json` 回执，拒绝覆盖、symlink、junction 和 reparse point。预检输出不回显 owner 名称、真实绝对路径、审批正文或业务值，只保留字段路径、规范原因码和输入包摘要。

合成隔离演练使用固定目标环境 `wp7-rehearsal`，拒绝 `MOSS_ENVIRONMENT=production`、相对路径、既有目录、symlink、junction 和 reparse point，也不读取正式 release-control DSN。成功回执必须同时披露 `rehearsal_only=true`、`synthetic_evidence=true`、`structure_only=true`、`integrity_only=true`、`authenticity_attested=false`、`release_gate_eligible=false`、`wp7_production_eligible=false` 和 `production_writes=false`。其中临时 SQLite 会写入合成 Manifest、Event 和 Alias，用来验证状态机；`production_writes=false` 的含义是没有连接或修改真实控制面、真实 DuckDB 或任何生产路径。`integrity_only=true` 表示自哈希只能发现意外漂移或未同步修改，不能证明签发者身份；外部权威签名必须等审批载体 owner 冻结后另行接入。

截至 2026-08-31，自动测试和一次手工隔离运行已经证明：三条 scope 可整体提升到候选 revision 2，再整体回切到基线 revision 3；候选 checksum 篡改和不完整 scope plan 均在状态变化前被拒绝；相同 rollback 幂等键重放不新增 Event 或 Alias；独立 verify 能发现回执、路径或 artifact checksum 漂移。这些证据不覆盖真实 writer 停写、真实备份恢复、兼容 API 启动、观察窗口、owner 决定或 RTO/RPO。

## 3. owner 填空

下面字段必须由 owner 在工单中补齐。任何一项仍为 `PENDING`，都不得进入试点执行阶段。

| 角色 | 填写内容 |
| --- | --- |
| 业务 owner | `PENDING` |
| 固收规则 owner | `PENDING` |
| 数据 owner | `PENDING` |
| 发布 owner | `PENDING` |
| 平台 / DBA owner | `PENDING` |
| 调度 owner | `PENDING` |
| worker owner | `PENDING` |
| 前端 owner | `PENDING` |
| 独立复核人 | `PENDING` |
| 审批权威载体 owner | `PENDING` |
| 备份操作员 | `PENDING` |
| 回滚执行人 | `PENDING` |

## 4. 环境与拓扑

本 runbook 只接受 owner 填写的绝对路径，不接受仓库默认值、相对路径、`~`、当前目录或未展开环境变量。以下路径均为模板，执行前必须由 owner 在工单中写成真实绝对路径。

| 项目 | 绝对路径 / 值 |
| --- | --- |
| 目标环境仓库根 | `PENDING`（本地编写路径不是生产路径） |
| `duckdb-main` 当前文件 | `PENDING` |
| `duckdb-main` previous sealed bundle | `PENDING` |
| candidate bundle | `PENDING` |
| rollback bundle 目录 | `PENDING` |
| governance 账本目录 | `PENDING` |
| 备份目录 | `PENDING` |
| receipt 目录 | `PENDING` |
| 日志目录 | `PENDING` |
| 兼容后端构建产物 | `PENDING` |
| 兼容前端构建产物 | `PENDING` |

拓扑只写成一件事就够：当前维护窗口必须是单实例 whole-bundle 窗口。若最终不是单实例，或不是同一物理整库文件，本文档不能直接复用，必须另起一份环境专用 runbook。

## 5. 停写证明

试点开始前，必须先证明所有写入口都已停写。证明不是一句“已经停了”，而是可以留档的回执、服务状态或队列状态。

| 对象 | 必须证明的事实 | 回执 / 证据字段 |
| --- | --- | --- |
| keepalive | 已暂停，不再触发自动恢复 | `PENDING: keepalive pause receipt` |
| scheduler | 已禁用或停止，不再投递新任务 | `PENDING: scheduler disable receipt` |
| supervisor | 已停，不会重启 worker / API | `PENDING: supervisor stop receipt` |
| queue | 队列已排空，没有待处理写任务 | `PENDING: queue drain receipt` |
| worker | 已停写，不再 materialize 或刷新共享 DuckDB | `PENDING: worker stop receipt` |
| API | 不再接受会写入 candidate 或 current 的路径 | `PENDING: api quiescence receipt` |
| 连接 | 目标库无活动写连接 | `PENDING: connection census` |
| WAL / journal | 没有继续增长的写日志 | `PENDING: WAL snapshot` |

停写证明的最低标准是：所有会写共享 DuckDB 的入口都已经关闭，且证明材料可以在回执里逐项勾稽。只停两个主进程不算进入维护窗口。

## 6. 备份与 checksum

进入试点前，必须先把可恢复性做成证据，而不是口头保证。至少要备份四类对象：物理整库、治理账本、部署配置、当前 alias / current 引用。

| 对象 | 备份要求 | 校验要求 |
| --- | --- | --- |
| `duckdb-main` 当前整库 | 完整文件级或对象级备份 | `PENDING: SHA256 / 对象版本 ID` |
| governance 账本 | 完整备份 | `PENDING: SHA256 / 对象版本 ID` |
| 部署配置 | 与 candidate 内容一致的冻结副本 | `PENDING: SHA256 / commit SHA` |
| current / previous alias 视图 | 备份当前状态 | `PENDING: revision + checksum` |
| candidate receipt | 归档到 receipt 目录 | `PENDING: receipt_sha256` |
| rollback plan | 归档到 receipt 目录 | `PENDING: plan_sha256` |

必须额外记录“恢复点”与“当前点”的对应关系。若同窗回切可用 previous sealed bundle，则 previous sealed bundle 的 checksum 与路径必须在备份包中出现；若进入 `forward_rebuild`，则最新整库与新的 rollback bundle 都要有独立 checksum。

## 7. 五态审批

五态审批是分层关系，不是同义词。一个状态通过，不代表下一个状态自动通过。这里采用 PRD 和执行方案里的五个状态名，任何别名都必须在工单里写成 `PENDING`。

| 状态 | 说明 | 典型证据 |
| --- | --- | --- |
| `evidence_captured` | 原始证据已采集并归档 | 运行回执、备份清单、停写证明 |
| `machine_validated` | 机器校验通过 | release control validate / release suite / contract receipt |
| `business_approved` | 业务 owner 已审阅并同意 | 结构化审批回执 |
| `formal_use_allowed` | 允许进入正式用途 | 受控试点授权回执 |
| `closure_approved` | 对应页面、口径或治理缺口已经由 owner 明确闭合 | 业务闭合记录、治理复核回执 |

五个状态必须全部披露，但是否作为本次提升的必需条件，以冻结 Manifest 与审批 registry 中的 `required_states` 为准；当前策略仍为 `PENDING`，不得自行删减。任一必需状态为 `PENDING` 或 `false` 时，都不能把试点称为“已获批”，也不能靠重跑脚本把它解释成 `true`。

## 8. 候选回执字段

候选与提升阶段应保存统一形状的回执。当前仓库里 `release_control.py` 已有 `prepare / validate / approve-record / promote / rollback / show` 子命令，回执至少应包含下面这些字段。

| 字段 | 说明 |
| --- | --- |
| `action` | `prepare` / `validate` / `approve-record` / `promote` / `rollback` / `show` |
| `outcome` | `applied` / `replayed` / `blocked` / `conflict` / `invalid` / `error` |
| `release_id` | 冻结后的发布编号 |
| `release_state` | candidate / validated / approved / current / rolled_back 等状态 |
| `manifest_digest` | 冻结的 manifest 摘要 |
| `target_environment` | 目标环境名称 |
| `idempotency_key` | 幂等键 |
| `replayed` | 是否回放既有结果 |
| `scopes` | scope 级别回执摘要 |
| `aliases` | current / previous alias 视图 |
| `blockers` | 阻断原因列表 |
| `details` | 附加证据，如备份、checksum、构建、审批、观察窗口 |

`details` 里至少还要放这几类内容：候选 bundle 路径、后端构建回执、前端构建回执、验证命令回执、审批回执、备份 checksum、当前和 previous alias 的 revision，以及如果发生回滚时的原因和 mode。

## 9. 试点阶段

### 阶段 A：前置校验

先确认 owner 字段不是 `PENDING`，再确认拓扑、路径、窗口和回执目录都已填成绝对路径。这个阶段的输出只应该是 `blocked`、`pending` 或 `passed` 的机器回执，不应该出现任何写动作。当前仓库的只读入口是 `scripts/wp7_fixed_income_pilot_preflight.py`；它只读取结构化交接包 JSON，默认模板保持 `blocked`，即使字段齐全也只会返回 `awaiting_owner_execution`，不会替代正式授权。

Go 条件：

- 生产拓扑、窗口、RTO / RPO、路径和 owner 全部已填。
- 停写证明已完整。
- 备份与 checksum 已完整。

Abort 条件：

- 任一 owner 或路径仍为 `PENDING`。
- 任何写入口未停。
- 备份校验失败。

### 阶段 B：候选构建

从最新静止点生成 `duckdb-main` candidate，只允许重建固定收益切片，不允许重新抓取或改写外部曲线，不允许把这个阶段写成整库热替换。

隔离候选入口及其 shadow-only 边界见 [固定收益 Whole-Bundle Shadow Candidate Runbook](../fixed_income_whole_bundle_shadow_runbook.md)。该入口的成功回执固定为 `release_gate_eligible=false`，只能进入后续证据审阅，不能单独推动提升。

必须附带的证据：

- candidate bundle 路径；
- candidate 的 checksum；
- 受控范围清单；
- 与 current / previous 的差异摘要；
- 若影响 API / DTO / 前端数值边界，则必须附带兼容后端 / 前端构建回执。

Go 条件：

- candidate 与 manifest 摘要一致。
- 目标范围与非目标范围都已核对。
- 后端 / 前端兼容构建没有阻断。

Abort 条件：

- candidate 不可复现。
- 非目标表出现漂移。
- 兼容构建不一致或缺失。

### 阶段 C：机器验证

机器验证只验证候选，不验证授权。建议把这一步拆成 release control validation、release suite、全历史对账、API / 页面 / 数值 smoke 和目标环境 readiness。

当前可确认的命令形状只有这些，不作为授权：

```powershell
.\.venv\Scripts\python.exe scripts/wp7_fixed_income_pilot_preflight.py --packet PENDING
.\.venv\Scripts\python.exe scripts/release_control.py validate --release-id PENDING --validation-file PENDING
.\.venv\Scripts\python.exe scripts/backend_release_suite.py --mcp-profile fast
.\.venv\Scripts\python.exe scripts/check_average_balance_business_owner_approval.py --require-captured
```

Go 条件：

- 所有机器验证回执都为通过。
- 审批材料结构完整。
- `machine_validated` 已由结构化回执记录。

Abort 条件：

- 任一回执失败、缺失或摘要漂移。
- 试点范围外的失败需要改写为“暂缓”，不能改写为“已通过”。

### 阶段 D：业务审批

业务审批只能基于已冻结候选摘要和已核对证据包，不得基于口头确认。

审批回执至少要把下列内容固定下来：权威审批主体引用、审批日期、审批结论、候选摘要、完整五态、registry 要求的状态子集，以及是否允许正式使用。应用只校验权威载体的结构化证明和摘要绑定，不自行断言审批人的真实身份。

Go 条件：

- registry 要求的每个状态均为 `true`，且五态没有相互推导。
- 当 `business_approved` 或 `formal_use_allowed` 属于 `required_states` 时，由 owner 显式写明为 `true`。
- 审批回执和 candidate 摘要绑定。

Abort 条件：

- 审批载体缺失。
- 审批人不是独立批准人。
- 任一 `required_states` 仍为 `false` 或 `PENDING`。

### 阶段 E：Go / No-Go

只有当前置校验、候选构建、机器验证和业务审批都完成时，才可以进入 Go / No-Go 判定。

Go 条件：

- 停写证明完整；
- 备份与 checksum 完整；
- candidate 回执完整；
- 五态完整披露，且 registry 要求的状态全部满足；
- 兼容后端 / 前端构建完整；
- 观察窗口和恢复步骤已填成绝对路径或明确工单引用。

No-Go 条件：

- 任何 `PENDING` 未闭合；
- 任何 checksum 不一致；
- 任何回执缺失；
- 任一必需审批状态未达标，或 `required_states` 尚未由 owner 冻结。

### 阶段 F：受控提升

提升前，必须先把 activation intent 写成候选文件的绝对路径，再把 `duckdb-main` 与全部 contained logical lane 一起作为完整 scope plan 提升。这里的关键不是“升一个表”，而是一次性处理整个计划中的 scope。

Go 条件：

- activation intent 与 manifest 一致；
- `scripts/release_control.py promote` 的 plan 文件与 candidate 一致；
- `duckdb-main` 和所有逻辑 lane 的 scope 都在同一事务里更新；
- 提升回执可追溯到 current / previous。

Abort 条件：

- scope plan 不完整；
- 任何 alias 只更新了一半；
- 发现部分 current 或 revision 冲突；
- 执行前已有其他域新的写入。

### 阶段 G：观察窗口

观察窗口的目的不是“等一等”，而是验证提升后系统仍然健康。窗口时长、监控项和报警阈值都必须由 owner 填成 `PENDING` 后再确认。

至少要观察这些事实：

- candidate release_id 是否被正确披露；
- API / 页面 / 数值 smoke 是否稳定；
- current 与 previous alias 是否正确；
- writer 恢复后文件 checksum 是否发生预期变化；
- 任何非目标表是否保持不变。

观察窗口的结束条件必须由人确认，不应只看脚本返回码。

## 10. 回滚判定

回滚分两种。

如果仍在同一停写窗口内，且其他域没有前进，可以走 `sealed_bundle_reactivate`，也就是回切到 previous sealed bundle。这个动作要求 previous sealed bundle 仍在备份里、checksum 可核对、且 current / previous 的事务回退没有引入新的写入。

如果 writer 已恢复，或者其他域已经有新写入，就不能再指向旧整库文件。这时只能走 `forward_rebuild`：以最新整库为底，重建新的 rollback bundle，恢复上一 approved 固定收益切片，再走完整校验与审批。

回滚的 `mode` 目前在 CLI 里只有两个可确认值：

```text
sealed_bundle_reactivate
forward_rebuild
```

这两个值只是命令形状，不是执行授权。

## 11. 阶段记录模板

每一阶段都要留下独立记录。下面模板只用于演练，不是生产命令。

```text
演练编号：PENDING
release_id：PENDING
维护窗口：PENDING
环境名称：PENDING
duckdb-main 当前路径：PENDING
duckdb-main previous sealed path：PENDING
candidate path：PENDING
rollback bundle path：PENDING
owner：PENDING
审批权威载体：PENDING

停写证明：
- keepalive：PENDING
- scheduler：PENDING
- supervisor：PENDING
- queue：PENDING
- worker：PENDING
- API：PENDING
- 连接：PENDING
- WAL：PENDING

备份与 checksum：
- duckdb-main checksum：PENDING
- governance checksum：PENDING
- 配置 checksum：PENDING
- alias revision：PENDING
- candidate receipt sha256：PENDING

五态审批：
- evidence_captured：PENDING
- machine_validated：PENDING
- business_approved：PENDING
- formal_use_allowed：PENDING
- closure_approved：PENDING

结果：
- go / no-go：PENDING
- 采用的回滚模式：PENDING
- 观察窗口结论：PENDING
- 恢复写入结论：PENDING
```

## 12. 退出标准

只有在下面所有条件都成立时，本 runbook 才能被标记为已完成：

1. owner、拓扑、路径、窗口和 RTO / RPO 不再是 `PENDING`。
2. 停写证明、备份、checksum、candidate receipt 和五态审批都已归档。
3. 成功路径与回滚路径都已分别验证，且明确区分 `sealed_bundle_reactivate` 与 `forward_rebuild`。
4. 兼容后端 / 前端构建与 release control 回执都能追溯到同一 candidate。
5. 观察窗口有明确结束回执，恢复写入后没有把新活动文件误记成 sealed immutable artifact。

在这些条件闭合前，本页只是一份受控演练模板，不是生产放行说明。
