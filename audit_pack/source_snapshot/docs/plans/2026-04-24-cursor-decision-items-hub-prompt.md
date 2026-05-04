# Cursor Prompt: Decision Items Hub Feature Surfacing

你在仓库 `F:\MOSS-V3` 工作。请按本 prompt 执行，并严格遵守仓库 `AGENTS.md`。

当前基准提交：

```text
b83ab2d Surface cross-asset research as a usable workbench
```

## 目标

把已经存在的后端「资产负债分析决策事项」能力做成一个可用的前端页面 `/decision-items`。

当前后端已有：

- `GET /ui/balance-analysis/decision-items`
- `POST /ui/balance-analysis/decision-items/status`
- `GET /ui/balance-analysis/dates`
- `GET /ui/balance-analysis/current-user`

当前前端已有 API client 和 types，但导航里的 `decision-items` 仍是 placeholder。你的任务是让它变成一个真正可用的决策事项工作台。

## 模型 / 子代理要求

如果 Cursor 支持子代理，请使用 `gpt-5.4` 模型，拆成 3-4 个并行子任务：

1. Repo mapper：只读确认 API/types/routes/tests 现状。
2. Page model executor：实现纯函数 page model 和单测。
3. Page UI/route executor：实现页面、路由、导航晋级。
4. Test fixer/verifier：补齐测试并跑验证。

不要让子代理改同一个文件造成冲突。若必须碰同一文件，先由一个子代理完成，其他子代理只读等待。

## 严格范围

只允许修改这些方向：

- `frontend/src/features/decision-items/**`
- `frontend/src/router/routes.tsx`
- `frontend/src/mocks/navigation.ts`
- `frontend/src/test/*DecisionItems*.test.tsx`
- `frontend/src/test/navigation.test.ts`
- `frontend/src/test/RouteRegistry.test.tsx`
- 必要时只做最小 `frontend/src/api/client.ts` / `frontend/src/api/contracts.ts` 测试修正

不要修改：

- `backend/**`
- 数据库 schema / migration
- auth / permission framework
- 全局 SDK wrapper 或大规模 api client 重构
- dashboard / balance-analysis 页面主体逻辑，除非只是为测试稳定做极小修正
- unrelated dirty files

注意：当前 worktree 很脏。不要 stage 或改写 unrelated dirty files。完成后不要 commit，留给 Codex final review。

## 先读这些文件

请先只读检查：

- `frontend/src/api/balanceAnalysisClient.ts`
- `frontend/src/api/client.ts`
- `frontend/src/api/contracts.ts`
- `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- `frontend/src/router/routes.tsx`
- `frontend/src/mocks/navigation.ts`
- `frontend/src/test/navigation.test.ts`
- `frontend/src/test/RouteRegistry.test.tsx`
- `frontend/src/test/ApiClient.test.ts`
- `backend/app/api/routes/balance_analysis.py`

重点确认现有方法：

- `client.getBalanceAnalysisDates()`
- `client.getBalanceAnalysisCurrentUser()`
- `client.getBalanceAnalysisDecisionItems({ reportDate, positionScope, currencyBasis })`
- `client.updateBalanceAnalysisDecisionStatus({ reportDate, positionScope, currencyBasis, decisionKey, status, comment })`

## 功能要求

### 1. 新建 page model

创建：

```text
frontend/src/features/decision-items/lib/decisionItemsPageModel.ts
```

模型职责：

- 输入 `BalanceAnalysisDecisionItemsPayload`、`result_meta`、current user，可选错误/加载状态。
- 输出页面 view model：
  - `reportDate`
  - `positionScope`
  - `currencyBasis`
  - `rows`
  - `summary`
  - `statusCounts`
  - `severityCounts`
  - `pendingRows`
  - `attentionRows`
  - `contractWarnings`
- 只做展示整理，不重算业务指标。
- 排序规则：
  - pending 在前
  - severity high > medium > low
  - 同级按 title / decision_key 稳定排序
- 字段完整性检查：
  - `decision_key`
  - `title`
  - `action_label`
  - `severity`
  - `reason`
  - `source_section`
  - `rule_id`
  - `rule_version`
  - `latest_status.status`
- 缺字段时不要崩溃，输出 `contractWarnings`，页面显式展示。

测试：

```text
frontend/src/test/decisionItemsPageModel.test.ts
```

至少覆盖：

- pending/high 排序优先级。
- pending/confirmed/dismissed 计数。
- high/medium/low 计数。
- 缺字段输出 contract warning。
- 空 rows 输出空态模型。

### 2. 新建 `/decision-items` 页面

创建：

```text
frontend/src/features/decision-items/pages/DecisionItemsPage.tsx
```

页面要回答的首要业务问题：

```text
今天有哪些跨页面决策事项需要处理，来源于哪条规则链路，当前处理状态是什么？
```

页面行为：

- 首屏顶部显示：
  - 报告日
  - 数据源模式 real/mock
  - 当前操作人
  - pending 总数
  - high severity 总数
  - result_meta trace/source/rule/cache 简要信息
- 默认报告日：
  - 优先从 `getBalanceAnalysisDates()` 取最新可用 report date。
  - 如果 dates 失败，允许显示错误态，不要写死日期。
- 控件：
  - report date select
  - position scope: `all` / `asset` / `liability`
  - currency basis: `CNY` / `native`
  - status filter: `all` / `pending` / `confirmed` / `dismissed`
  - severity filter: `all` / `high` / `medium` / `low`
- 主列表：
  - title
  - severity
  - action_label
  - reason
  - source_section
  - rule_id
  - rule_version
  - latest status
  - updated_by / updated_at
- 行为：
  - 选中一条 row，在右侧或下方 detail panel 展示完整字段。
  - comment textarea。
  - `确认` 按钮调用 `updateBalanceAnalysisDecisionStatus(... status: "confirmed")`
  - `忽略` 按钮调用 `updateBalanceAnalysisDecisionStatus(... status: "dismissed")`
  - 更新中 disable 对应行按钮。
  - 成功后 refetch decision items 和 current user。
  - 失败时在页面显式展示错误，不吞掉。
- 状态：
  - loading
  - API error
  - no dates
  - no decision items
  - contract warning
  - mock mode warning

UI 要求：

- 不做营销页，不做 hero landing。
- 使用现有 `PageHeader` / design tokens / workbench shell 习惯。
- 卡片 radius 不超过现有系统风格，避免嵌套卡片。
- 不要新增依赖。
- 不要把中文再搞成 mojibake；新增文案请保持 UTF-8 正常中文。

建议 test ids：

- `decision-items-page`
- `decision-items-report-date`
- `decision-items-position-scope`
- `decision-items-currency-basis`
- `decision-items-status-filter`
- `decision-items-severity-filter`
- `decision-items-summary-pending`
- `decision-items-summary-high`
- `decision-items-list`
- `decision-items-row-${index}`
- `decision-items-detail`
- `decision-items-confirm-${index}`
- `decision-items-dismiss-${index}`
- `decision-items-error`
- `decision-items-contract-warning`

### 3. 接入路由和导航

修改：

```text
frontend/src/router/routes.tsx
frontend/src/mocks/navigation.ts
```

要求：

- lazy import `DecisionItemsPage`。
- `/decision-items` 渲染真实页面，不再 placeholder。
- 将 `workbenchNavigation` 中 `decision-items` 从 `placeholder/Reserved` 晋级到：
  - `readiness: "live"`
  - `readinessLabel: "Temporary"`
  - `governanceStatus: "temporary-exception"`
  - `readinessNote` 说明它已接 `balance-analysis decision-items` 读写链路。
- 如果有临时例外测试清单，把 `decision-items` 加入 temporary exception keys。
- 不新增旧路径 alias，除非已有测试明确需要。

### 4. 测试

新增：

```text
frontend/src/test/DecisionItemsPage.test.tsx
frontend/src/test/DecisionItemsRoute.test.tsx
frontend/src/test/decisionItemsPageModel.test.ts
```

更新：

```text
frontend/src/test/navigation.test.ts
frontend/src/test/RouteRegistry.test.tsx
```

测试至少覆盖：

- route `/decision-items` 渲染真实页面。
- navigation 将 `decision-items` 放进 primary/live，不再 secondary/placeholder。
- 页面从 dates 默认选择最新 report date，并用该日期请求 decision items。
- 切换 position scope / currency basis 会重新请求。
- status/severity filter 正常筛选。
- confirm/dismiss 调用 update API，payload 包含 reportDate、positionScope、currencyBasis、decisionKey、status、comment。
- update 成功后 refetch。
- update 失败展示错误。
- empty rows 展示空态。
- contract warning 可见。

不要依赖真实后端。用 mocked `ApiClient`。

## 验证命令

在 `frontend` 下执行：

```powershell
npx vitest run src/test/decisionItemsPageModel.test.ts src/test/DecisionItemsPage.test.tsx src/test/DecisionItemsRoute.test.tsx src/test/navigation.test.ts src/test/RouteRegistry.test.tsx src/test/ApiClient.test.ts src/test/BalanceAnalysisPage.test.tsx
```

```powershell
npx eslint src/features/decision-items/pages/DecisionItemsPage.tsx src/features/decision-items/lib/decisionItemsPageModel.ts src/router/routes.tsx src/mocks/navigation.ts src/test/DecisionItemsPage.test.tsx src/test/DecisionItemsRoute.test.tsx src/test/decisionItemsPageModel.test.ts
```

```powershell
npx tsc --noEmit
```

回到 repo 根目录后执行：

```powershell
git diff --check -- frontend/src/features/decision-items frontend/src/router/routes.tsx frontend/src/mocks/navigation.ts frontend/src/test/DecisionItemsPage.test.tsx frontend/src/test/DecisionItemsRoute.test.tsx frontend/src/test/decisionItemsPageModel.test.ts frontend/src/test/navigation.test.ts frontend/src/test/RouteRegistry.test.tsx
```

## 完成报告

完成后不要 commit。请报告：

- 改了哪些文件。
- 页面现在暴露了哪些后端能力。
- 运行了哪些验证命令，结果是什么。
- 是否有未解决风险。
- `git status --short` 中哪些是本次任务文件，哪些是原有 unrelated dirty files。

## 禁止事项

- 不要修 backend。
- 不要顺手重构 `BalanceAnalysisPage.tsx` 大组件。
- 不要 stage unrelated dirty files。
- 不要新增依赖。
- 不要用假数据替代 API 结果作为真实业务判断。
- 不要把 placeholder 页面包装成“已完成”；必须有真实 read/write API 链路。
