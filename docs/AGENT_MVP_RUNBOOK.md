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
3. 可选：`MOSS_AGENT_PROVIDER` —— `local`（默认，工具链路）、`hermes` 或 `dexter`。
4. 可选：`MOSS_AGENT_RUN_QUEUED_TIMEOUT_SECONDS` —— `queued` 状态 run 的超时秒数（缺省 600，正式 settings 字段 `agent_run_queued_timeout_seconds`），超时后读取状态会收敛为 `failed`（见下文 runs 端点）。
5. **多进程部署必须设置** `MOSS_AGENT_ACTION_TOKEN_SECRET`（settings 字段 `agent_action_token_secret`）：suggested action 确认 token 的 HMAC secret。未配置时回退进程本地随机值，API 进程与 worker 进程各自持有不同 secret，`/runs` 链路签发的确认 token 将无法在 API 进程校验通过。单进程本地开发可不配置。
6. 生产部署必须显式设置 `MOSS_ENVIRONMENT=production`：`environment` 缺省值为 `development`，该值同时参与 dev bypass 守卫判定（见下）。

### Agent 开发完整栈

使用 `scripts\\dev-agent-up.ps1`（或双击 `scripts\\dev-agent-up.cmd`）启动 Agent-enabled API、worker 和 frontend。该入口显式设置 `MOSS_AGENT_ENABLED=true`、`MOSS_AGENT_DEV_SCOPE_BYPASS=true`、`MOSS_DEV_API_SCRIPT=dev-agent-api.ps1` 和 `VITE_MOSS_AGENT_FRONTEND_ENABLED=true`，然后复用 `dev-up.ps1` 的 Postgres、health/readiness、worker heartbeat、frontend 和重复进程保护。

普通 `scripts\\dev-up.ps1` 保持 `dev-api.ps1` 默认值，不会自动开启 Agent。为避免把任意脚本名传入后台启动器，`MOSS_DEV_API_SCRIPT` 仅允许 `dev-api.ps1` 或 `dev-agent-api.ps1`。

**dev bypass 生效条件（三重守卫）**：`MOSS_AGENT_DEV_SCOPE_BYPASS=true` 仅在 `environment=development` **且**请求来自 loopback 客户端（127.0.0.1/::1）时跳过 agent 资源的 scope 鉴权；bypass 开启时非 loopback 请求一律 403 并记录警告日志，不会回落到 scope 鉴权。生产环境显式设置 `MOSS_ENVIRONMENT=production` 后该开关整体失效。

禁用或未启用时，Agent URL 不注册，`POST /api/agent/query` 返回 **HTTP 404**，OpenAPI 也不包含 `/api/agent*`。

---

## 端点

`POST /api/agent/query`

- Content-Type: `application/json`
- 请求体：见后端 **`backend/app/agent/schemas/agent_request.py::AgentQueryRequest`**
- 成功：**HTTP 200**，正文 **`AgentEnvelope`**
- **失败也留审计**：local 工具链路执行失败（如无可用 `report_date` 的 ValueError）会先写入 `agent_audit`（`result_kind=agent.query_failed`、`quality_flag=error`、`tools_used` 含 `status:failed` 与 `provider:local`）再返回 404/503；只记录异常类型（`error_type`），不复制可能含敏感信息的原始错误正文。Hermes/Dexter 链路的成功、fallback 与失败路径同样各自写审计。

`POST /api/agent/runs`（异步）

- 支持 `MOSS_AGENT_PROVIDER=local`（含默认）、`hermes`、`dexter`。executor 分流与 `/query` 完全一致：governed intent / research workflow / 分析闲聊类请求强制走 local 工具链（`execute_agent_query`），否则按 provider 分发。
- 成功：**HTTP 200**，正文 **`AgentRunCreateResponse`**（含 `run_id`、`status=queued`）。
- 执行记录追加写入治理 JSONL 流 `agent_run`；local 托管运行的 `provider` 字段如实记为 `local`。
- 同一 `run_id` 会写入成功或失败的 `agent_audit` 记录，可与 `agent_run` 直接关联；失败终态与失败审计原子追加，且只记录异常类型，不复制可能含敏感信息的原始错误正文。
- 前端兼容性：此前 `local` 返回 400，前端 Workbench 以该 400 作为回退 `/query` 的信号；local 放行后前端不再收到 400，回退逻辑自然不再触发，属兼容变化（前端代码无需改动）。

`GET /api/agent/runs/{run_id}`

- 返回 **`AgentRunStatusResponse`**：`queued / starting / running / completed / failed` 与最终 `AgentEnvelope`（completed 时）。
- 仅 run 的发起用户可查询（owner 校验）。
- `starting / running` 超过对应 Hermes/Dexter 运行超时再加 30 秒宽限期仍未进入终态时，读取状态会以条件追加方式写入 `failed` 终态与关联审计；跨线程/进程使用同一治理目录锁，`completed / failed / cancelled` 均为不可逆终态。`local` 没有外部 provider 超时，不套用该阈值。
- **queued 超时收敛**：`queued` 状态超过 `agent_run_queued_timeout_seconds`（缺省 600 秒）仍未开始执行时，读取状态会条件追加 `failed` 终态与关联审计（`error_type=StaleQueuedAgentRun`），避免排队 run 永久悬挂。

`GET /api/agent/runs`

- 返回当前用户的 run 列表（`limit` 1-100，缺省 20；可按 `conversation_id` 过滤，会话须归属当前用户）。

`POST /api/agent/runs/{run_id}/cancel`

- 仅 owner 可取消；`queued / starting / running` 可取消为 `cancelled`（不可逆终态），其他状态返回 409。
- **取消释放执行槽**：执行监督循环每 0.5 秒轮询 run 终态，观察到 `cancelled` 后立即返回并释放 worker 执行槽；仍在途的外部 provider 调用在守护线程中自然收尾，不再占用执行资源。

`POST /api/agent/runs/{run_id}/retry`

- 仅 owner 可重试；仅 `failed / cancelled` 终态可重试（生成新 `run_id`），其他状态返回 409。

`GET /api/agent/runs/{run_id}/events`（SSE）

- 以 `text/event-stream` 推送 run 状态快照，进入终态后结束。
- **keepalive 心跳**：快照无变化时每 15 秒发送一条 SSE 注释帧（`: keepalive`），防止空闲代理断开连接；EventSource 类解析器原生忽略注释帧，不影响事件契约。

工作台端点：`/api/agent/projects`、`/api/agent/projects/{id}/conversations` 等 workspace 端点与 agent 路由同挂载、同受 `MOSS_AGENT_ENABLED` 与 agent scope 鉴权（读 `agent:read`、写 `agent:write`）约束。

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
      "type": "execute_intent",
      "label": "Execute first mapped intent: pnl_summary",
      "payload": { "intent": "pnl_summary" },
      "requires_confirmation": true,
      "confirmation_token": "agent_action:v1:<expires_at>:<hmac_sha256_hex>"
    }
  ]
}
```

说明：`result_meta` 继承通用 **`ResultMeta`**，具体字段以运行时 JSON 为准。当前实际签发的 suggested action type 为 `execute_intent`、`inspect_drill`、`inspect_news_events`。

---

## Suggested action 确认（服务端强制）

- 需确认的动作由服务端签发 **`confirmation_token`**（HMAC-SHA256，绑定 type/label/payload/过期时间，TTL 15 分钟）。
- 客户端确认执行时，把动作原样连同 token 提交回 `/query`（或 `/runs`）：`context.suggested_action` + `context.suggested_action_confirmation_token`。
- **确认要求由服务端目录决定**（`backend/app/agent/runtime/action_token.py::CONFIRMATION_REQUIRED_ACTION_TYPES`，当前为 `execute_intent` / `inspect_drill` / `inspect_news_events`）：命中目录的动作即使客户端剥离 `requires_confirmation` 声明也必须携带有效 token，缺失/伪造/过期/与动作不匹配一律 403。目录只允许收紧。
- 动作 payload 可内嵌 **`confirmation_scope`**（如 `user_id` / `run_id`）：scope 属于 payload，由同一 HMAC 保护，篡改 scope 即校验失败。
- token secret 来源：`agent_action_token_secret`（settings，经 `MOSS_AGENT_ACTION_TOKEN_SECRET` 环境变量注入）；未配置时回退进程本地随机值，**跨进程校验会失败**（见「本地启用」第 5 条）。

---

## 安全边界

- **只读**：Agent MVP 设计为从已有 DuckDB / 治理链路读取并组装答案，不在浏览器端执行任意 SQL。
- **不执行客户端传来的 SQL**：前端与请求体均不应携带可执行 SQL 并由服务端直接执行（服务端工具链内部生成的审计字段 `sql_executed` 仅用于披露）。
- **不通过本接口触发 refresh / 写入任务**：驾驶舱 **`AgentPanel`** 仅展示建议动作 chip，不触发写入副作用。
- **审计全覆盖**：成功、失败、disabled、run 终态均写 `agent_audit`（唯一正式入口 `append_agent_audit`；run 终态为保证原子性与终态同锁追加，payload 契约一致）；失败记录只含异常类型，不含原始错误正文。
- **确认边界在服务端**：需确认的 suggested action 以服务端目录 + HMAC token 强制，客户端声明不再是控制边界（见上节）。
- **禁用模式**：`MOSS_AGENT_ENABLED=false` 时 router 不注册，Agent URL 返回 404 且不进入 OpenAPI；路由级 503/audit 仅是显式挂载场景的二次防线。

---

## Disabled 模式（404 / 未注册）

前端应提示「Agent 当前未启用」，而不是当作 **`AgentEnvelope`** 解析。

---

## Agent run 流压缩（手动运维动作）

用途：控制 `data/governance/agent_run.jsonl` 与 `agent_run_dispatch.jsonl` 体积。终态且最后写入超过保留窗口（默认 7 天，可用 `agent_run_stream_retention_days` 覆盖）的 run 仅保留最后终态快照，删除行归档至同目录 `<stream>.archive.jsonl`，不丢数据。

- 触发：`python -c "from backend.app.governance.settings import get_settings; from backend.app.tasks.agent_run_stream_compaction import compact_agent_run_streams; print(compact_agent_run_streams(settings=get_settings()))"`；或经 broker 派发 actor `compact_agent_run_streams`（`worker_bootstrap` 已注册）。
- 验证：命令输出/日志中的 `runs_compacted` 与 `*_archived` 计数；`agent_run_compaction.jsonl` 追加了对应统计事件；抽查任一被压缩 run 的 `GET /api/agent/runs/{run_id}` 仍返回终态快照。
- 安全性：压缩幂等可重跑；执行期间持有 run 状态迁移锁，进行中的 run 写入会短暂等待；归档文件只增不删，如需彻底清理由治理流程另行决定。建议在低峰执行。

## 故障排查

| 现象 | 可能原因 | 建议 |
|------|-----------|------|
| HTTP 404，OpenAPI 无 `/api/agent*` | `MOSS_AGENT_ENABLED` 未打开 | 这是当前默认发布边界；只有取得明确试点授权后才可设为 `true` 并重启后端 |
| HTTP 503，正文非 disabled JSON | 运行时错误（如 Hermes 超时）；参见 `RuntimeError` 路径 | 查后端日志、`MOSS_AGENT_PROVIDER` 与 Hermes 配置 |
| 返回「无报告日期」类 **ValueError** | 某仓库无可用 `report_date` | 确认 DuckDB 批次与日期列表接口 |
| `result_kind` 为 **`agent.unknown`** | 问题未匹配任一关键字且未指定 `context.intent` | 调整提问措辞或显式 intent |
| **`quality_flag` 为 stale / warning** | 数据陈旧或治理降级 | 对照 `result_meta` 与 evidence，勿当作正式发布的唯一依据 |
| run 长期停在 `queued` 后变 `failed`（`StaleQueuedAgentRun`） | worker 未消费或排队超过 `agent_run_queued_timeout_seconds`（缺省 600 秒） | 检查 worker 进程/心跳；确需更长排队时间时调大该配置 |
| 确认 suggested action 返回 403（`confirmation token`） | token 缺失/过期（15 分钟）/与动作不匹配；或多进程部署未配置统一 `MOSS_AGENT_ACTION_TOKEN_SECRET` | 重新获取动作与 token；多进程部署为 API 与 worker 配置同一 secret 并重启 |
| bridge 模式 Hermes 持续降级，日志出现 `Hermes bridge at ... rejects this process's token` | 后端曾非优雅退出（kill -9/崩溃），上一进程的孤儿 bridge 仍占用端口并持旧一次性 token；新进程令牌不匹配被 403 | 按 bridge 端口找到孤儿进程并停掉（正常重启已由 lifespan 自动关停托管 bridge）；长期自管的外部 bridge 应配置固定 `HERMES_BRIDGE_TOKEN` 供各后端进程共用 |

### Hermes 失败分类码（日志与审计）

Hermes 链路失败时，后端日志（`error_code=...`）与 `agent_audit` 的 `result_meta.error_code` 会带运维分类码，用于区分失败通道：

- `hermes_timeout`：CLI/bridge 请求超时，或 bridge 未在期限内就绪；
- `hermes_spawn_failed`：命令不存在或子进程/bridge 拉起失败；
- `hermes_exit_failed`：hermes 进程非零退出，或 bridge 就绪前意外退出；
- `hermes_bridge_unauthorized`：bridge 拒绝本进程 token（403，见上表孤儿 bridge 场景）。

分类码只进日志与审计；对外 `AgentEnvelope` 的 `fallback_reason` 保持粗粒度契约 `hermes_runtime_unavailable` 不变。

WSL 部署下，`HERMES_BRIDGE_TOKEN` 不进入 `wsl.exe` 命令行（避免本机进程列表可见），而是写入 `WSLENV`（`HERMES_BRIDGE_TOKEN/u`）由 wsl.exe 以环境变量穿透到 WSL 侧 bridge 进程；非 WSL 场景该变量无副作用。

---

## 相关测试（后端）

```bash
uv run --project backend python -m pytest tests/test_agent_api_contract.py tests/test_agent_intent_routing.py -q
```

治理与安全侧（审计契约、白名单、bypass 守卫、确认 token、settings 契约）：

```bash
uv run --project backend python -m pytest tests/test_agent_audit_log_contract.py tests/test_agent_toolset_policy.py tests/test_agent_dev_bypass_guard.py tests/test_agent_action_token.py tests/test_agent_api.py tests/test_settings_contract.py -q
```

期望：现有契约与路由测试全部通过。
