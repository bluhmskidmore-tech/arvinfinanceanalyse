# Cursor Prompt: Agent MVP 前端 Tasks 4-7

> 直接粘贴到 Cursor 的 chat 框执行。

---

你正在 `F:\MOSS-V3` 仓库工作。

## 背景

后端 Agent MVP Tasks 1-3 已由 Hermes 完成（28 tests passed）。
完整上下文在：

```
docs/handoff/2026-04-25-agent-mvp-cursor-codex-handoff.md
docs/plans/2026-04-25-moss-read-only-agent-mvp.md
```

**先读这两个文件，再开始实现。**

---

## 执行前必做

```bash
git status --short
```

仓库有大量无关脏文件，**不要碰它们**。只改本任务列出的文件。

---

## 后端已完成的内容（不要重做）

- `POST /api/agent/query` 已注册，`MOSS_AGENT_ENABLED=false` 时返回 503
- `AgentEnvelope` 已包含 `answer / cards / evidence / result_meta / next_drill / suggested_actions`
- `AgentSuggestedAction` schema 已存在
- 后端测试：`tests/test_agent_api_contract.py` + `tests/test_agent_intent_routing.py` → 28 passed

---

## Task 4 — 前端 Agent API Client

**新建：**
- `frontend/src/api/agentClient.ts`

**修改：**
- `frontend/src/api/client.ts`（只做组合，不堆大块逻辑）
- `frontend/src/api/contracts.ts`（如需共享类型）
- `frontend/src/test/AgentClient.test.ts`（新建）

**`agentClient.ts` 实现要求：**

```ts
// POST ${baseUrl}/api/agent/query
queryAgent(request: AgentQueryRequest): Promise<AgentEnvelope>
```

请求类型：
```ts
type AgentQueryRequest = {
  question: string;
  basis?: "formal" | "scenario" | "analytical";
  filters?: Record<string, unknown>;
  position_scope?: string;
  currency_basis?: string;
  context?: Record<string, unknown>;
};
```

响应类型（对应后端 AgentEnvelope）：
```ts
type AgentEnvelope = {
  answer: string;
  cards: unknown[];
  evidence: {
    tables_used: string[];
    filters_applied: Record<string, unknown>;
    sql_executed: string[];
    evidence_rows: number;
    quality_flag: string;
  };
  result_meta: {
    trace_id: string;
    basis: string;
    result_kind: string;
    formal_use_allowed: boolean;
    source_version: string;
    vendor_version: string;
    rule_version: string;
    cache_version: string;
    quality_flag: string;
    scenario_flag: boolean;
    tables_used: string[];
    filters_applied: Record<string, unknown>;
    sql_executed: string[];
    evidence_rows: number;
    next_drill: unknown[];
  };
  next_drill: unknown[];
  suggested_actions: Array<{
    type: string;
    label: string;
    payload: Record<string, unknown>;
    requires_confirmation: boolean;
  }>;
};
```

**行为要求：**
- 503 disabled 响应 → 返回友好错误，不 crash
- mock 模式 → 返回稳定的 mock AgentEnvelope（answer 写"Agent 当前为演示模式"）
- `client.ts` 只做 `queryAgent = agentClient.queryAgent.bind(agentClient)` 式组合，不堆实现

**验证：**
```bash
cd frontend && npm run test -- AgentClient --pool=forks --poolOptions.forks.singleFork=true
cd frontend && npm run test -- ApiClient --pool=forks --poolOptions.forks.singleFork=true
cd frontend && npm run typecheck
```

---

## Task 5 — 最小可复用 AgentPanel 组件

**新建：**
- `frontend/src/features/agent/AgentPanel.tsx`
- `frontend/src/features/agent/AgentPanel.css`（样式放 CSS，不堆 inline style）
- `frontend/src/test/AgentPanel.test.tsx`

**Props：**
```ts
type AgentPanelProps = {
  pageId: string;
  reportDate?: string | null;
  currentFilters?: Record<string, unknown>;
  defaultQuestion?: string;
};
```

**行为要求：**
- 用户可输入问题，Submit 调用 `client.queryAgent`
- context 必须包含：`page_id` / `report_date` / `current_filters`
- 显示 loading 态
- 显示 answer
- 显示紧凑 evidence：至少 `quality_flag` + `tables_used`
- 显示 `suggested_actions`（被动 chips，不执行后端副作用，不触发 refresh）
- 503 disabled → 显示"Agent 当前未启用"友好提示，不报错

**测试覆盖：**
1. 渲染输入框和提交按钮
2. 提交后显示 answer
3. 显示 evidence quality_flag
4. suggested_actions 渲染为 chips
5. 503 disabled 显示友好提示
6. loading 态

**验证：**
```bash
cd frontend && npm run test -- AgentPanel --pool=forks --poolOptions.forks.singleFork=true
cd frontend && npm run typecheck
```

---

## Task 6 — 挂载到 DashboardPage

**修改：**
- `frontend/src/features/workbench/pages/DashboardPage.tsx`（或对应路径，先确认实际文件位置）
- 对应的 `DashboardPage.test.tsx`

**要求：**
- 在页面底部或侧边加入 `<AgentPanel pageId="dashboard" reportDate={reportDate} currentFilters={currentFilters} />`
- 布局简单，不加大量 inline style
- 不全局挂载（不改 WorkbenchShell）
- 更新/新增页面测试，确认 AgentPanel 渲染

**验证：**
```bash
cd frontend && npm run test -- DashboardPage --pool=forks --poolOptions.forks.singleFork=true
cd frontend && npm run typecheck
cd frontend && npm run debt:audit
```

---

## Task 7 — Agent Runbook 文档

**新建：**
- `docs/AGENT_MVP_RUNBOOK.md`

**必须包含：**
- 本地启用方式：`MOSS_AGENT_ENABLED=true`
- 端点：`POST /api/agent/query`
- 支持的 intents（从 `agent_service.py` 读取实际支持列表）
- 请求/响应示例（用后端 AgentEnvelope 真实结构）
- 安全边界（只读、不执行 SQL、不触发 refresh）
- disabled 模式说明
- 故障排查：503 disabled / 无报告日期 / unknown intent / stale quality_flag

---

## 最终回归验证

```bash
cd frontend && npm run test -- AgentClient AgentPanel DashboardPage --pool=forks --poolOptions.forks.singleFork=true
cd frontend && npm run typecheck
cd frontend && npm run debt:audit
```

后端回归（确认 Hermes 的工作没被破坏）：
```bash
uv run --project backend python -m pytest tests/test_agent_api_contract.py tests/test_agent_intent_routing.py -q
```

期望：28 passed

---

## 绝对禁止

- 不加任意 SQL Agent
- 不接入 LLM provider
- 不从 panel 触发 write/refresh 动作
- 不全局挂载到 WorkbenchShell
- 不重构无关 API client 或页面布局
- 不碰无关脏文件（cross-asset / market-data / macro / bond-analytics 等）

---

## 完成后输出格式

```
Implemented Agent MVP frontend Tasks 4-7.

Changed files:
- ...

What changed:
- ...

Validation:
- command -> result

Known risks / follow-up:
- ...
```
