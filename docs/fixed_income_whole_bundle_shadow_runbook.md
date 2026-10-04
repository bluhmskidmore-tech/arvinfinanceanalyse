# 固定收益 Whole-Bundle Shadow Candidate Runbook

这份 runbook 只定义固定收益试点的维护窗口、影子证据构建和回滚分叉原则，不授权任何生产切换。当前仓库已具备 `scripts/bond_risk_shadow_candidate.py` 的单报告日隔离候选，以及 `scripts/bond_risk_shadow_batch.py` 的多报告日结构证据聚合；后者为每个日期创建独立 candidate，并不证明一个 `duckdb-main` candidate 已完成全历史重建。API 与 worker 仍共享可写 DuckDB，因此这两类工具都只能作为 whole-bundle 维护流程中的前置证据，不能单独当成 lane 级发布脚本使用。

当前结论很简单：可以做单日期影子候选、可以聚合多日期结构证据、可以做差异验证和摘要绑定，但尚未形成单 candidate 全历史重建证明。只要生产拓扑、owner 批准、观察窗口或恢复路径还是 `PENDING`，就必须停在证据审阅阶段，不能进入 promote。

## 适用边界

本 runbook 只适用于以下场景：

- 目标是验证固定收益 formal 链路在共享 DuckDB 静止点上的候选重建。
- 物理切换范围是整库 `duckdb-main`，不是单表、单文件或单 lane 热替换。
- writer 可以进入单实例维护窗口，且业务接受 API 与 worker 暂停。

以下场景不适用：

- 想在不停写条件下热切换 `data/moss.duckdb`。
- 想只替换 `fact_formal_bond_analytics_daily` 或 `fact_formal_risk_tensor_daily` 而不验证整库其他表。
- 想在生产环境直接跑影子脚本并把输出目录当成 current。

## 前置门禁

进入维护窗口前，必须同时满足这些条件：

- 已有一个冻结的 source DuckDB 静止点，且不是 `get_settings().duckdb_path` 当前 live 路径。
- `scripts/bond_risk_shadow_candidate.py` 只会写显式 `--output-dir`，不会写 live DuckDB；如果 source 等于 live 路径、环境是 `production`、governance backend 是 SQL、或 source schema 不是 current，脚本会 fail-closed。
- 发布 owner、金融规则 owner、数据 owner、业务 owner 和回滚批准人都已命名；任何一项缺失都视为 `PENDING`。
- 已确认 previous approved `release_id`、其 `duckdb-main` 物理 bundle 和逻辑 lane current 全都可定位。
- 已准备整库备份、治理 JSONL 备份、部署配置备份和观察窗口。

## 维护窗口顺序

先停写，再构建候选，再验候选，最后才讨论切换。顺序不能倒。

1. 停止 keepalive、Windows Scheduler、外部 supervisor、新任务入队和所有会写共享 DuckDB 的入口，等待活动 writer 排空。
2. 停止 worker，再停止 API，确认目标 DuckDB 没有活动连接。
3. 对当前整库、治理目录、部署配置和 release alias 做只读留痕与离线备份。
4. 从最新静止点复制整库，准备一个全新的 shadow 输出目录。
5. 在影子目录中运行：

```powershell
.\.venv\Scripts\python.exe scripts/bond_risk_shadow_candidate.py `
  --report-date <PENDING_APPROVED_REPORT_DATE> `
  --source-duckdb-path <PENDING_ABSOLUTE_SEALED_COPY_PATH> `
  --expected-source-sha256 <PENDING_APPROVED_SOURCE_SHA256> `
  --output-dir <PENDING_NEW_ABSOLUTE_OUTPUT_DIRECTORY>
```

以上只展示参数形状；尖括号字段必须由获批工单替换，不能原样执行。输出目录必须是本次运行新建的独占目录，source 不能位于其中。

如果需要按明确清单逐日收集结构证据，先准备一个 UTF-8 日期文件，每行只能有一个 `YYYY-MM-DD`，不允许空行、重复或隐式日期推导，然后运行：

```powershell
.\.venv\Scripts\python.exe scripts/bond_risk_shadow_batch.py `
  --report-dates-file <PENDING_ABSOLUTE_APPROVED_DATES_FILE> `
  --source-duckdb-path <PENDING_ABSOLUTE_SEALED_COPY_PATH> `
  --expected-source-sha256 <PENDING_APPROVED_SOURCE_SHA256> `
  --batch-output-dir <PENDING_NEW_ABSOLUTE_REPO_OUTPUT_OR_TMP_DIRECTORY>
```

单日期回执 schema 固定为 `moss.bond-risk-shadow-candidate-receipt/v1`，批次回执 schema 固定为 `moss.bond-risk-shadow-batch-receipt/v1`。批次回执同时声明 `candidate_model=per_report_date_isolated_candidates`、`history_coverage=multi_report_date_structural_shadow_only` 和 `not_a_single_candidate_full_history_rebuild=true`。任一日期失败时，其他日期继续执行并形成 `partial` 或 `failed` 回执，但无论全部成功还是部分成功，`release_gate_eligible`、`financial_golden_validated` 和 `wp7_eligible` 都保持 `false`。

6. 单日期模式检查输出目录中的 `bond_risk_shadow_candidate_receipt.json`；批次模式先检查顶层 `bond_risk_shadow_batch_receipt.json`，再按其中记录逐一复验每个日期子目录里的 `bond_risk_shadow_candidate_receipt.json`。只有单日期回执自哈希、candidate 摘要、`.SEALED` marker 相互绑定且 `.INCOMPLETE` 不存在时，对应子目录才算完成结构性封存；它还必须同时证明：

- `shadow_only=true`
- `release_gate_eligible=false`
- source 文件前后 `sha256` 完全一致
- catalog identity 一致
- 除 `fact_formal_bond_analytics_daily` 和 `fact_formal_risk_tensor_daily` 的目标 `report_date` 外，没有其他表漂移

7. 用影子 candidate 继续执行 formal receipts、OpenAPI base-ref diff、前端 numeric、页面/API smoke、治理审计和 owner 审阅。
8. 所有摘要、审批和观察窗口都齐备后，才允许在独立 release control 流程里追加 approval 与 activation intent；本 runbook 本身不执行 promote。

## 影子候选的验收口径

影子脚本的成功不等于生产可切。它只回答两件事：第一，固定收益链路能否在隔离副本上按既有任务入口跑通；第二，这次重建有没有把非目标域一起带坏。

验收时要重点看三类证据。第一类是 source 不变，说明候选构建没有误写 live 文件。第二类是非目标表恒等，说明这不是一次整库污染。第三类是两张目标 facts 的非目标日恒等，说明变化被限制在本次批准的 `report_date` 切片内。

如果候选 receipt 没能同时给出这三类证据，就把这次运行定性为失败 candidate，而不是“部分成功”。

## Promote 之前还缺什么

即使影子 candidate 全绿，下面这些条件缺一项也不能 promote：

- Manifest、approval registry、authority receipt 和 approval gate 全部通过。
- 生产拓扑、观察窗口、RTO/RPO 和恢复步骤都有 owner 批准。
- current 与 previous 的 `duckdb-main` alias compare-and-swap 计划已冻结。
- 切换后的 API 隔离验收命令、页面 smoke 和 current readiness 复验路径都已明确。

这些条件里只要还有 `PENDING`，状态就只能写“控制面能力已建、正式推广未完成”。

## 回滚分叉

回滚要先判断其他域有没有前进，不能一律“切回旧文件”。

如果仍在同一停写窗口内，且没有任何其他域写入新 current，可以按 compare-and-swap 回切 previous sealed `duckdb-main`，恢复兼容构建，再复验 current readiness。

如果 writer 已恢复，或者其他域已经在新 current 上前进，就不能直接指回旧整库文件。此时必须从最新整库重新生成 rollback bundle，把上一 approved 固定收益切片恢复进去，重新完成 schema、整库 identity、formal receipts、审批和 activation，再按同样维护流程切换。

失败 candidate、失败原因和所有 release 事件都要保留，不能清空历史来“重试得更干净”。

## 明确禁止

- 禁止在 `production` 环境直接运行 shadow candidate 脚本。
- 禁止把 live `duckdb_path` 作为 `--source-duckdb-path`。
- 禁止把 shadow candidate 输出目录直接写进 current 配置并绕过 release control approval。
- 禁止在 API 或 worker 仍连接目标库时替换 `duckdb-main`。
- 禁止把影子脚本的成功表述成“系统已支持长期 immutable snapshot 发布”。

当前更准确的表述是：固定收益单报告日隔离候选、多报告日结构证据聚合与非目标漂移验证已经具备；单 candidate 全历史重建、金融差异门和正式切换仍未完成，并继续受维护窗口、owner 批准和共享可写文件边界约束。
