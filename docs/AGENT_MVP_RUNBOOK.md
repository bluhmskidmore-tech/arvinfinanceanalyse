# Agent MVP Runbook

本文描述 MOSS 只读 Agent 端点的启用方式、请求与响应形态，以及在 **`backend/app/services/agent_service.py`**（本地 DuckDB 工具链路）下注册的意图（intent）处理清单。

Hermes 模式（`MOSS_AGENT_PROVIDER=hermes`）走 **`backend/app/services/hermes_agent_service.py`**：路由方式与自然语言提示构造不同于下面的关键字路由表；仍以 **`AgentEnvelope`** 为响应外壳。

---

## 当前发布边界（2026-07-25）

- Agent MVP / Phase 4 尚未获得当前 repo-wide Phase 2 的发布授权，生产默认必须保持 `MOSS_AGENT_ENABLED=false`。
- 禁用时，Agent router 不会导入或注册；`/api/agent*` 返回 HTTP 404，并且不会出现在 OpenAPI 中。
- 路由内部保留的 503 disabled response 仅作为显式挂载 router 时的二次防线，不代表当前生产发布面仍公开 Agent URL。
- `MOSS_AGENT_ENABLED=true` 只用于获得明确授权后的隔离试点或本地验证；设置环境变量本身不构成业务 owner 或发布批准，修改后必须重启后端。

---

## 本地启用

1. 环境变量前缀为 **`MOSS_`**（见 `backend/app/governance/settings.py`）。
2. 启用 Agent API：
   - `MOSS_AGENT_ENABLED=true`
3. 可选：`MOSS_AGENT_PROVIDER` —— `local`（默认，工具链路）或 `hermes`。

### Agent 开发完整栈

使用 `scripts\\dev-agent-up.ps1`（或双击 `scripts\\dev-agent-up.cmd`）启动 Agent-enabled API、worker 和 frontend。该入口显式设置 `MOSS_AGENT_ENABLED=true`、`MOSS_AGENT_DEV_SCOPE_BYPASS=true`、`MOSS_DEV_API_SCRIPT=dev-agent-api.ps1` 和 `VITE_MOSS_AGENT_FRONTEND_ENABLED=true`，然后复用 `dev-up.ps1` 的 Postgres、health/readiness、worker heartbeat、frontend 和重复进程保护。

普通 `scripts\\dev-up.ps1` 保持 `dev-api.ps1` 默认值，不会自动开启 Agent。为避免把任意脚本名传入后台启动器，`MOSS_DEV_API_SCRIPT` 仅允许 `dev-api.ps1` 或 `dev-agent-api.ps1`。

禁用或未启用时，Agent URL 不注册，`POST /api/agent/query` 返回 **HTTP 404**，OpenAPI 也不包含 `/api/agent*`。

---

## 端点

`POST /api/agent/query`

- Content-Type: `application/json`
- 请求体：见后端 **`backend/app/agent/schemas/agent_request.py::AgentQueryRequest`**
- 成功：**HTTP 200**，正文 **`AgentEnvelope`**

`POST /api/agent/runs`（异步）

- 支持 `MOSS_AGENT_PROVIDER=local`（含默认）、`hermes`、`dexter`。executor 分流与 `/query` 完全一致：governed intent / research workflow / 分析闲聊类请求强制走 local 工具链（`execute_agent_query`），否则按 provider 分发。
- 成功：**HTTP 200**，正文 **`AgentRunCreateResponse`**（含 `run_id`、`status=queued`）。
- 执行记录追加写入治理 JSONL 流 `agent_run`；local 托管运行的 `provider` 字段如实记为 `local`。
- 同一 `run_id` 会写入成功或失败的 `agent_audit` 记录，可与 `agent_run` 直接关联；失败终态与失败审计原子追加，且只记录异常类型，不复制可能含敏感信息的原始错误正文。
- 前端兼容性：此前 `local` 返回 400，前端 Workbench 以该 400 作为回退 `/query` 的信号；local 放行后前端不再收到 400，回退逻辑自然不再触发，属兼容变化（前端代码无需改动）。

`GET /api/agent/runs/{run_id}`

- 返回 **`AgentRunStatusResponse`**：`queued / starting / running / completed / failed` 与最终 `AgentEnvelope`（completed 时）。
- 仅 run 的发起用户可查询（owner 校验）。
- `starting / running` 超过对应 Hermes/Dexter 运行超时再加 30 秒宽限期仍未进入终态时，读取状态会以条件追加方式写入 `failed` 终态与关联审计；跨线程/进程使用同一治理目录锁，`completed / failed` 均为不可逆终态。`local` 没有外部 provider 超时，不套用该阈值；`queued` 可能正等待进程内串行执行，也不按该阈值误判。

认证与安全上下文：后端会通过 **`AuthContext`** 合并 **`context`**（如 `user_id`、`user_role`）；`run_id` 是服务端保留字段，客户端提交的同名值会在 API 边界移除，再由 `/runs` 托管链路注入。不要把 Agent 当作绕过权限或伪造审计关联的渠道。

---

## 支持的 intents（`agent_service.py` 注册的工具处理器）

下列字符串为 **`ToolRegistry`** 中注册的 intent 名称（由 **`AnalysisViewTool`** 根据问题关键字或 `context.intent` 解析后分发）：

| Intent | 说明（概要） |
|--------|----------------|
| `gitnexus_status` | GitNexus / 仓库图谱状态类查询 |
| `portfolio_overview` | 组合概览 / 资产负债规模 |
| `pnl_summary` | 损益汇总 |
| `duration_risk` | 久期 / DV01 等利率风险摘要 |
| `credit_exposure` | 信用敞口 |
| `product_pnl` | 产品分类损益 |
| `pnl_bridge` | PnL 桥接 / 归因 |
| `risk_tensor` | 风险张量 |
| `market_data` | 市场数据 |
| `news` | 新闻 |
| `research_radar_brief` | 研究速读（治理 Choice 新闻事件之上的本地分析简报，`formal_use_allowed=false`） |

关键字路由（摘自 **`backend/app/agent/tools/analysis_view_tool.py`** 的 `_INTENT_PATTERNS`）：例如问题中含「组合概览」「资产规模」→ `portfolio_overview`；含「久期」「DV01」→ `duration_risk`。无法匹配时 intent 为 **`unknown`**，返回解释性答案而非 DuckDB 深度结果。

也可在请求的 **`context.intent`** 中显式指定 intent（需与后端路由约定一致）。

### Workflow（plan / execute 双模式）

- 金融 workflow：slash 命令 `/portfolio-review`、`/pnl-review`、`/risk-memo`、`/market-brief` 或 `context.workflow_id`。默认返回 **plan 卡**（`result_kind=agent.workflow.<id>`，`formal_use_allowed=false`）；`context.workflow_mode="execute"` 时按目录顺序执行映射 intents 并返回汇总。详见 `docs/agent_financial_workflows.md`。
- 研究 workflow：`/research-radar`、关键字「研究速读」「研究雷达」或 `context.workflow_id="research_radar_brief"`。默认同样返回 plan 卡；`context.workflow_mode="execute"` 时执行 `research_radar_brief` handler。显式 `context.intent="research_radar_brief"` 保持既有语义：直接执行简报（不经 plan 卡）。
- 所有 workflow 结果均为 `formal_use_allowed=false`，不新增写路径、不触发副作用。

### 证据披露（`sql_executed`）

`evidence.sql_executed` 是历史契约名，前端按“只读 SQL 披露”展示。Dexter 研究上下文、新闻和产品损益等同源路径披露实际送入只读执行层的参数化模板；部分 local intent（如组合概览、PnL 汇总、风险摘要、桥接和市场数据）披露与业务结果对齐的主干/等价模板，不应把它当作完整查询日志或可重放审计。`?` 只表示绑定参数位置，不披露参数值；业务过滤摘要见 `filters_applied`。

所有披露均由服务端生成并只保留 `SELECT / WITH`；服务端从不执行客户端传入的 SQL。结构防漂移测试会校验只读性、来源表和关键过滤字段，真实执行同源路径另由执行测试覆盖。

`evidence_strength` 区分 `governed_moss`（受治理本地证据）、`provider_runtime`（仅外部模型运行证据）、`local_fallback`（未运行受治理查询）和 `mixed`（外部模型基于 MOSS 只读上下文生成）。`mixed` 仍不可视为正式受治理结论。

---

## 请求示例

```json
{
  "question": "2026-03-31 的组合概览是什么？",
  "basis": "formal",
  "filters": {},
  "position_scope": "all",
  "currency_basis": "CNX",
  "context": {
    "page_id": "dashboard",
    "report_date": "2026-03-31",
    "current_filters": { "allow_partial": false }
  }
}
```

字段缺省时后端使用 **`AgentQueryRequest`** 中的默认值（与 Python 模型一致）。

---

## 响应示例（`AgentEnvelope`）

结构与 **`backend/app/agent/schemas/agent_response.py`** 一致：顶层包含 **`answer`**、**`cards`**、**`evidence`**、**`result_meta`**、**`next_drill`**、**`suggested_actions`**。

```json
{
  "answer": "……自然语言结论……",
  "cards": [
    { "type": "metric", "title": "示例", "value": "0" }
  ],
  "evidence": {
    "tables_used": ["fact_formal_bond_analytics_daily"],
    "filters_applied": {},
    "sql_executed": [],
    "evidence_rows": 0,
    "quality_flag": "ok"
  },
  "result_meta": {
    "trace_id": "tr_……",
    "basis": "formal",
    "result_kind": "agent.duration_risk",
    "formal_use_allowed": true,
    "source_version": "sv_……",
    "vendor_version": "vv_none",
    "rule_version": "rv_agent_mvp_v1",
    "cache_version": "cv_……",
    "quality_flag": "ok",
    "vendor_status": "ok",
    "fallback_mode": "none",
    "scenario_flag": false,
    "generated_at": "2026-05-07T12:00:00Z",
    "tables_used": ["fact_formal_bond_analytics_daily"],
    "filters_applied": {},
    "sql_executed": [],
    "evidence_rows": 0,
    "next_drill": []
  },
  "next_drill": [],
  "suggested_actions": [
    {
      "type": "inspect_lineage",
      "label": "查看来源",
      "payload": {},
      "requires_confirmation": true
    }
  ]
}
```

说明：`result_meta` 继承通用 **`ResultMeta`**，具体字段以运行时 JSON 为准。

---

## 安全边界

- **只读**：Agent MVP 设计为从已有 DuckDB / 治理链路读取并组装答案，不在浏览器端执行任意 SQL。
- **不执行客户端传来的 SQL**：前端与请求体均不应携带可执行 SQL 并由服务端直接执行（服务端工具链内部生成的审计字段 `sql_executed` 仅用于披露）。
- **不通过本接口触发 refresh / 写入任务**：驾驶舱 **`AgentPanel`** 仅展示建议动作 chip，不触发写入副作用。
- **禁用模式**：`MOSS_AGENT_ENABLED=false` 时 router 不注册，Agent URL 返回 404 且不进入 OpenAPI；路由级 503/audit 仅是显式挂载场景的二次防线。

---

## Disabled 模式（404 / 未注册）

前端应提示「Agent 当前未启用」，而不是当作 **`AgentEnvelope`** 解析。

---

## 故障排查

| 现象 | 可能原因 | 建议 |
|------|-----------|------|
| HTTP 404，OpenAPI 无 `/api/agent*` | `MOSS_AGENT_ENABLED` 未打开 | 这是当前默认发布边界；只有取得明确试点授权后才可设为 `true` 并重启后端 |
| HTTP 503，正文非 disabled JSON | 运行时错误（如 Hermes 超时）；参见 `RuntimeError` 路径 | 查后端日志、`MOSS_AGENT_PROVIDER` 与 Hermes 配置 |
| 返回「无报告日期」类 **ValueError** | 某仓库无可用 `report_date` | 确认 DuckDB 批次与日期列表接口 |
| `result_kind` 为 **`agent.unknown`** | 问题未匹配任一关键字且未指定 `context.intent` | 调整提问措辞或显式 intent |
| **`quality_flag` 为 stale / warning** | 数据陈旧或治理降级 | 对照 `result_meta` 与 evidence，勿当作正式发布的唯一依据 |

---

## 相关测试（后端）

```bash
uv run --project backend python -m pytest tests/test_agent_api_contract.py tests/test_agent_intent_routing.py -q
```

期望：现有契约与路由测试全部通过。
