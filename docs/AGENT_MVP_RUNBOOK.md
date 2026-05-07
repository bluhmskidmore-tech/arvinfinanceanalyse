# Agent MVP Runbook

本文描述 MOSS 只读 Agent 端点的启用方式、请求与响应形态，以及在 **`backend/app/services/agent_service.py`**（本地 DuckDB 工具链路）下注册的意图（intent）处理清单。

Hermes 模式（`MOSS_AGENT_PROVIDER=hermes`）走 **`backend/app/services/hermes_agent_service.py`**：路由方式与自然语言提示构造不同于下面的关键字路由表；仍以 **`AgentEnvelope`** 为响应外壳。

---

## 本地启用

1. 环境变量前缀为 **`MOSS_`**（见 `backend/app/governance/settings.py`）。
2. 启用 Agent API：
   - `MOSS_AGENT_ENABLED=true`
3. 可选：`MOSS_AGENT_PROVIDER` —— `local`（默认，工具链路）或 `hermes`。

禁用或未启用时，`POST /api/agent/query` 返回 **HTTP 503**，正文为 **`AgentDisabledResponse`**（例如含 `"enabled": false`）。

---

## 端点

`POST /api/agent/query`

- Content-Type: `application/json`
- 请求体：见后端 **`backend/app/agent/schemas/agent_request.py::AgentQueryRequest`**
- 成功：**HTTP 200**，正文 **`AgentEnvelope`**

认证与安全上下文：后端会通过 **`AuthContext`** 合并 **`context`**（如 `user_id`、`user_role`）；不要把 Agent 当作绕过权限的渠道。

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

关键字路由（摘自 **`backend/app/agent/tools/analysis_view_tool.py`** 的 `_INTENT_PATTERNS`）：例如问题中含「组合概览」「资产规模」→ `portfolio_overview`；含「久期」「DV01」→ `duration_risk`。无法匹配时 intent 为 **`unknown`**，返回解释性答案而非 DuckDB 深度结果。

也可在请求的 **`context.intent`** 中显式指定 intent（需与后端路由约定一致）。

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
- **禁用模式**：`MOSS_AGENT_ENABLED=false` 时接口返回 503，并写入审计（见 `audit_disabled_agent_query`）。

---

## Disabled 模式（503）

响应示例（节选）：

```json
{
  "enabled": false,
  "phase": "phase1",
  "detail": "Agent endpoint is planned but disabled in Phase 1."
}
```

前端应提示「Agent 当前未启用」，而不是当作 **`AgentEnvelope`** 解析。

---

## 故障排查

| 现象 | 可能原因 | 建议 |
|------|-----------|------|
| HTTP 503，`enabled: false` | `MOSS_AGENT_ENABLED` 未打开 | 设为 `true` 并重启后端 |
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
