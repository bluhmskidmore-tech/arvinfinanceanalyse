# Hermes 金融审计员工集群

这个入口把现有 Hermes 团队底座包装成 MOSS V3 专用的金融系统审计员工体。它会生成总控看板、角色 prompt、任务箱、汇报箱、启动脚本和网页控制台。

## 一键生成

在仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-moss-finance-audit-cluster.ps1 -PrepareOnly
```

默认生成到：

```text
.omx/hermes-teams/moss-finance-audit-cluster/
```

核心文件：

- `TEAM_BOARD.md`：总控看板。
- `dashboard.html`：本地网页控制台。
- `manifest.json`：角色、启动器、队列和集群配置。
- `prompts/*.md`：每个员工的职能 prompt。
- `inbox/*.md`：每个员工的任务箱。
- `outbox/*.md`：每个员工的汇报箱。
- `launch/*.ps1`：每个员工的 Hermes 启动脚本。

## 启动网页控制台

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-team-dispatch.ps1 -TeamId moss-finance-audit-cluster
```

打开后可以在网页里选择角色、填写任务、派发任务。派发会写入对应员工的 inbox，并唤醒对应启动脚本。

## 启动员工窗口

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-moss-finance-audit-cluster.ps1 -Launch
```

如果只想先启动核心固收审计小组：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-moss-finance-audit-cluster.ps1 -Launch -Roles lead,fixed-income-analyst,data-lineage-auditor,metric-caliber-officer,valuation-accounting-reconciler,pnl-attribution-analyst,risk-manager,qa
```

## 默认员工

- `lead`：总控负责人，拆任务、收 outbox、维护 P0/P1/P2 清单。
- `product-manager`：业务问题和 owner 签字边界。
- `metric-caliber-officer`：指标口径、单位、日期、正式/候选/排除状态。
- `data-lineage-auditor`：数据血缘、source_version、fallback/stale、DuckDB 证据。
- `fixed-income-analyst`：固收口径、clean/dirty、应计利息、久期、凸性、YTM、DV01。
- `asset-liability-manager`：资产负债、净敞口、币种折算、ALM 结论。
- `valuation-accounting-reconciler`：估值、会计、514/516/517、符号和正式 PnL 来源。
- `pnl-attribution-analyst`：PnL bridge、carry、action attribution、residual。
- `risk-manager`：DV01、KRD、久期、凸性、CS01、风险披露。
- `market-data-specialist`：曲线、FX、价格、估值源、report_date。
- `backend-api-contract-engineer`：API 契约、result_meta、source_lineage。
- `developer`：审计结论后的最小修复。
- `frontend-developer`：API 到页面的显示链路。
- `ui-ux-page-closer`：首屏结论、无数据、stale、fallback、definition pending。
- `security-permission-auditor`：权限、写入路径、脚本和审计记录。
- `code-reviewer`：独立审查 diff 和测试缺口。
- `qa`：验证矩阵和失败证据。
- `docs-delivery-manager`：签字包、交付包、最终汇总。

## 推荐派发模板

### 固收 P0 口径论证

派给 `fixed-income-analyst`：

```text
标题：固收 P0：clean/dirty、应计利息、久期、凸性、DV01 口径论证

请审计 bond analytics 相关文档、测试、后端 core_finance、API、前端显示链路。
重点回答：
1. market_value 是 clean 还是 dirty？
2. accrued_interest 是否进入 dirty/carry/action attribution？
3. day-count、YTM、久期、凸性的复利规则是什么？
4. DV01 是否按 CNY/1bp 披露？

必须输出：结论、证据、P0/P1/P2、涉及文件/表/接口、验证命令、需要 owner 签字的点。
不要猜正式业务口径；证据不足就标 pending。
```

### 外币债券是否已折人民币

派给 `data-lineage-auditor`：

```text
标题：核实外币债券是否已经转换为人民币

请用本地 schema、文档、测试、DuckDB 实库证据核实 bond analytics 中外币债券的 FX 转换链路。
重点追踪字段：currency、market_value、fx_rate、report_date、as_of_date、source_version、fallback/stale。
MCP 证据工具如果不可用，必须写明不可用，并记录替代证据和残余风险。
```

### 页面业务指标闭环

派给 `frontend-developer` 或 `ui-ux-page-closer`：

```text
标题：页面指标闭环：API 到图表/表格

请追踪 API response -> adapter/transformer -> state/selector -> component -> chart/table。
检查单位、精度、null/0/undefined/NaN、币种、日期、fallback、stale、definition pending。
不要在前端新造正式指标；发现后端契约缺口就回派 backend-api-contract-engineer。
```

## 员工汇报格式

每个员工都写到自己的 `outbox/<role>.md`：

```md
## 结论

## 证据

## 问题级别

## 涉及文件/表/接口

## 验证命令

## 阻塞/需 owner 签字

## 给 Leader 的下一步建议
```

## 收口方式

1. Leader 先派固收 P0 首轮。
2. 各员工写 outbox，不互相改对方汇报。
3. Leader 合并出 P0/P1/P2 和 owner 签字清单。
4. 只有证据充分且范围明确的问题才交给 `developer` 或 `frontend-developer` 修复。
5. `code-reviewer` 和 `qa` 对修复做独立复核。
6. `docs-delivery-manager` 汇总签字包和剩余风险。

## 注意事项

- 业务口径不明确时，不猜。
- MCP 不可用时，不等于可以跳过证据；改用本地 schema、文档、测试和 DuckDB，并记录残余风险。
- 不碰数据库 schema、权限框架、调度、全局 SDK 包装层，除非 Leader 明确指出那是根因。
- 不要用 `git add .`；这个仓库经常有大量并行工作。
