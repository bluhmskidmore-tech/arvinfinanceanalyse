# Agent MVP Runbook

本文描述 MOSS 只读 Agent 端点的启用方式、请求与响应形态，以及在 **`backend/app/services/agent_service.py`**（本地 DuckDB 工具链路）下注册的意图（intent）处理清单。

Hermes 模式（`MOSS_AGENT_PROVIDER=hermes`）走 **`backend/app/services/hermes_agent_service.py`**：路由方式与自然语言提示构造不同于下面的关键字路由表；仍以 **`AgentEnvelope`** 为响应外壳。

Pi 模式（`MOSS_AGENT_PROVIDER=pi`）走 **`backend/app/services/pi_agent_service.py`**：通过 `pi --mode rpc` 执行单轮叙事回答，Pi 侧工具、扩展、skills 和上下文文件均关闭，仍以 **`AgentEnvelope`** 为响应外壳。Jev 默认关闭；shadow/active 只有显式配置后才会读取 Jev 决策，active 在 Jev 不可用或低置信度时拒绝进入 Pi。

---

## 当前发布边界（2026-07-25）

- Agent MVP / Phase 4 尚未获得当前 repo-wide Phase 2 的发布授权，生产默认必须保持 `MOSS_AGENT_ENABLED=false`。
- 禁用时，Agent router 不会导入或注册；`/api/agent*` 返回 HTTP 404，并且不会出现在 OpenAPI 中。
- 路由内部保留的 503 disabled response 仅作为显式挂载 router 时的二次防线，不代表当前生产发布面仍公开 Agent URL。
- `MOSS_AGENT_ENABLED=true` 只用于获得明确授权后的隔离试点或本地验证；设置环境变量本身不构成业务 owner 或发布批准，修改后必须重启后端。

### 本机 MOSS Chat 发布（2026-09-06）

本次按用户授权，将 MOSS Chat 开放到本机 `5888` 的打包预览服务。前端使用 `VITE_MOSS_AGENT_FRONTEND_ENABLED=true` 显式开启侧边栏入口、`/agent` 和已有业务页助手；开发模式与生产构建采用同一开关，缺省或非 `true` 值仍关闭。`/agent-lab` 继续要求开发模式。

本机发布开关保存在 `frontend/.env.production.local`。该文件不入库；其他部署需在自己的构建环境显式设置同名变量。修改开关后重新构建并启动对应产物，单独重启旧预览包不会改变编译后的开关值。

本机启动程序通过 `scripts/dev_runtime_control.py` 的发布登记选择构建目录。新包须生成完整文件 SHA-256 清单，按 `enter`、`select-frontend`、`leave` 流程登记，再由 `scripts/dev-frontend.ps1` 启动，最后运行 `frontend-probe` 核对实际响应与登记产物一致。仅替换 `5888` 进程会被自动恢复流程切回旧包。本节所述 2026-09-06 构建当时位于 `.codex-tmp/moss-chat-stable-home-20260906/dist`，并非持续有效的当前登记地址；实际选择以 `tmp-governance/runtime-clean/control/frontend.json` 及其清单为准。

首次 Chat 发布误将工作区内待开发首页一并打包，现已撤下该包。该次恢复包从 `f75503d7` 的已提交前端单独构建，只叠加 Chat 发布改动及旧发布已经验收的两处市场来源文案；首页与旧发布布局一致。后续定向发布须使用独立源码快照并列明允许叠加的文件，不能直接打包含有其他在途页面改动的工作区。开发中的首页源码不因本次恢复而回退。

截至 2026-09-27 的只读核对，登记选择的是 `.codex-tmp/portfolio-release-20260926/frontend-source/frontend/dist`，清单为同一发布目录下的 `manifest.json`；当时 `5888` 无监听。本轮收口源码尚未切换到该入口，日后仍须用 `frontend-probe` 核对实际响应，不以此处日期代替运行探针。

这次发布沿用已启用的本机 Agent API，不变更 `MOSS_AGENT_ENABLED`、身份权限、只读工具约束或结果披露。`5888` 的生产构建表示前端打包模式，不能替代后端生产部署所需的认证配置和发布授权。验收时须同时确认侧边栏入口、对话提交与结果返回，不能只以表单可见判断可用。

---

## 本地启用

1. 环境变量前缀为 **`MOSS_`**（见 `backend/app/governance/settings.py`）。
2. 启用 Agent API：
   - `MOSS_AGENT_ENABLED=true`
3. 可选：`MOSS_AGENT_PROVIDER` —— `local`（默认，工具链路）、`hermes`、`dexter` 或 `pi`。
4. 可选：`MOSS_AGENT_RUN_QUEUED_TIMEOUT_SECONDS` —— `queued` 状态 run 的超时秒数（缺省 600，正式 settings 字段 `agent_run_queued_timeout_seconds`），超时后读取状态会收敛为 `failed`（见下文 runs 端点）。
5. **多进程部署必须设置** `MOSS_AGENT_ACTION_TOKEN_SECRET`（settings 字段 `agent_action_token_secret`）：suggested action 确认 token 的 HMAC secret。`environment=development` 下未配置时回退进程本地随机值并告警，API 进程与 worker 进程各自持有不同 secret，`/runs` 链路签发的确认 token 将无法在 API 进程校验通过；**`environment=production` 下未配置则 fail-closed**：签发抛 `RuntimeError`、校验抛 `PermissionError`（错误信息指向该环境变量），不再回退随机值。单进程本地开发可不配置。
6. 生产部署必须显式设置 `MOSS_ENVIRONMENT=production`：`environment` 缺省值为 `development`，该值同时参与 dev bypass 守卫判定（见下）。

### Pi + Jev 本地试点

Pi 试点仍需显式设置 `MOSS_AGENT_ENABLED=true`，并将 `MOSS_AGENT_PROVIDER=pi`；可按本机安装方式设置 `MOSS_AGENT_PI_COMMAND`、`MOSS_AGENT_PI_MODEL` 和 `MOSS_AGENT_PI_TIMEOUT_SECONDS`。Windows 后端默认使用 `pi.cmd`，Linux/macOS 默认使用 `pi`。缺省 `MOSS_AGENT_JEV_MODE=off`，因此既不会调用 Jev，也不会改变现有 provider 行为。

如果 Pi 使用当前 MOSS 进程的 provider 登录，需要在已获授权的本机试点中额外设置 `MOSS_AGENT_PI_FORWARD_API_KEY=true`。该开关根据 `MOSS_AGENT_PI_MODEL` 的 provider 前缀，只把对应的父进程凭据放入 Pi 子进程环境（目前支持 OpenAI、Anthropic、xAI、MiniMax），不写入 MOSS 配置、不写入审计、不传给 Jev；缺省值为 `false`，Hermes 和 Dexter 不受影响。

需要观察 Jev 但不让它改变执行结果时，设置 `MOSS_AGENT_JEV_MODE=shadow` 和 `TYPESAFE_API_KEY`。适配器只向 Jev 发送路由与语义元数据，不发送用户问题、filters、页面选中行或金融数值；Jev 的结果只进入审计/披露字段。`active` 只适合完成 shadow 校验并获得单独授权后使用，Jev 缺 key、超时、返回非法 route 或置信度不足时会 fail-closed，Pi 不会被调用。

### Agent 开发完整栈

使用 `scripts\\dev-agent-up.ps1`（或双击 `scripts\\dev-agent-up.cmd`）启动 Agent-enabled API、worker 和 frontend。该入口显式设置 `MOSS_AGENT_ENABLED=true`、`MOSS_AGENT_DEV_SCOPE_BYPASS=true`、`MOSS_DEV_API_SCRIPT=dev-agent-api.ps1` 和 `VITE_MOSS_AGENT_FRONTEND_ENABLED=true`，然后复用 `dev-up.ps1` 的 Postgres、health/readiness、worker heartbeat、frontend 和重复进程保护。

普通 `scripts\\dev-up.ps1` 保持 `dev-api.ps1` 默认值，不会自动开启 Agent。为避免把任意脚本名传入后台启动器，`MOSS_DEV_API_SCRIPT` 仅允许 `dev-api.ps1` 或 `dev-agent-api.ps1`。

**dev bypass 生效条件（三重守卫）**：`MOSS_AGENT_DEV_SCOPE_BYPASS=true` 仅在 `environment=development` **且**请求来自 loopback 客户端（127.0.0.1/::1）时跳过 agent 资源的 scope 鉴权；bypass 开启时非 loopback 请求一律 403 并记录警告日志，不会回落到 scope 鉴权。生产环境显式设置 `MOSS_ENVIRONMENT=production` 后该开关整体失效。

原生 `scripts/dev-api.ps1`（包括 `dev-agent-api.ps1` 委托启动）强制选择 `MOSS_LOCAL_ONLY_API=1`。变量未设置时由脚本启用；继承的关闭或非法值会中止启动，随后用所选 Python 解析实际 Settings 再核对策略已生效。Linux 原生手动启动同一策略时使用 `MOSS_ENVIRONMENT=development MOSS_LOCAL_ONLY_API=1 backend/.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 7888`。通用 Settings 的该字段默认关闭，现有 Compose 的容器间代理与 `0.0.0.0` 容器内监听保持原契约，不属于原生单机入口。

本机策略启用后，开发 API 在业务中间件之前校验客户端和实际连接的本地地址均为回环，Host 必须为 localhost 或回环地址且端口匹配 API。请求带 Origin 或 Referer 时，其来源也必须为本机；跨站浏览器请求缺少两者时会被拒绝。现有 Vite 代理不生成 Forwarded 来源头，本机 API 拒绝 Forwarded、X-Forwarded-* 和 X-Real-IP。源码预览默认 5890 和自选本机端口可继续使用同源代理，跨源响应仍按原 CORS 白名单处理。这是本机操作系统会话边界，不是多人认证，也不支持把透明远程代理接到本机 API。

本机策略还会在开发应用启动时禁止开启 `MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST`，要求开发 CORS 配置为明确本机来源，并要求 Uvicorn CLI 的显式 host 和 `UVICORN_HOST` 为回环。隔离测试可沿用独立的身份头注入，不启动受信任本机应用。该策略保留现有匿名身份和受守卫保护的 Agent 本机 bypass，避免改变已有工作区归属；非开发部署继续使用原启动限制和授权机制。修改入口代码后需通过既有运行登记协调重启，不能凭源码修改声明已生效。

禁用或未启用时，Agent URL 不注册，`POST /api/agent/query` 返回 **HTTP 404**，OpenAPI 也不包含 `/api/agent*`。

---

## 端点

`POST /api/agent/query`

- Content-Type: `application/json`
- 请求体：见后端 **`backend/app/agent/schemas/agent_request.py::AgentQueryRequest`**
- 成功：**HTTP 200**，正文 **`AgentEnvelope`**
- **失败也留审计**：local 工具链路执行失败（如无可用 `report_date` 的 ValueError）会先写入 `agent_audit`（`result_kind=agent.query_failed`、`quality_flag=error`、`tools_used` 含 `status:failed` 与 `provider:local`）再返回 404/503；只记录异常类型（`error_type`），不复制可能含敏感信息的原始错误正文。Hermes/Dexter 链路的成功、fallback 与失败路径同样各自写审计；**provider 审计写入本身失败时 fail-closed**：不再返回未留痕的应答，而是记录 `error_type` 后抛 `RuntimeError`（路由映射为 503）。
- **多轮上下文由服务端重建**：请求带 `context.conversation_id` 时，`/query`、`/runs`、`/lab/runs` 与 retry 都会先校验会话归属（外来或不存在的 `conversation_id` 返回 403/404），再从 workspace 会话消息重建 `context.conversation.recent_turns`（最近 4 轮已完成的 question/answer，分别截断到 800/1400 字）并**覆盖**客户端传入的同名字段；不带 `conversation_id` 时保持客户端值。历史重建发生在语义快照固定与 intent 资源授权之前。

`POST /api/agent/runs`（异步）

- 支持 `MOSS_AGENT_PROVIDER=local`（含默认）、`hermes`、`dexter`、`pi`。executor 分流与 `/query` 完全一致：governed intent / research workflow / 分析闲聊类请求强制走 local 工具链（`execute_agent_query`），否则按 provider 分发。
- 成功：**HTTP 200**，正文 **`AgentRunCreateResponse`**（含 `run_id`、`status=queued`）。
- 执行记录追加写入治理 JSONL 流 `agent_run`；local 托管运行的 `provider` 字段如实记为 `local`。
- **派发两阶段落盘**：`agent_run_dispatch` 流在 broker `send` 之前先写 `phase="requested"`，`send` 成功后再写 `phase="accepted"`；无 `phase` 字段的历史行按 accepted 解释。等待派发确认时，若已有 `requested` 行且随后观察到 `starting/running/终态`，视为隐式 acceptance，不再误报派发失败。
- 同一 `run_id` 会写入成功或失败的 `agent_audit` 记录，可与 `agent_run` 直接关联；失败终态与失败审计原子追加，且只记录异常类型，不复制可能含敏感信息的原始错误正文。
- 前端兼容性：此前 `local` 返回 400，前端 Workbench 以该 400 作为回退 `/query` 的信号；local 放行后前端不再收到 400，回退逻辑自然不再触发，属兼容变化（前端代码无需改动）。

`GET /api/agent/runs/{run_id}`

- 返回 **`AgentRunStatusResponse`**：`queued / starting / running / completed / failed` 与最终 `AgentEnvelope`（completed 时）。
- 仅 run 的发起用户可查询（owner 校验）。owner 校验与状态读取合并为一次流读取（`get_agent_run_owner_and_status`），events 与 retry 同样单次读取；cancel 端点仍保留两次读取（受既有契约测试的 monkeypatch 约束）。
- `starting / running` 超过对应 Hermes/Dexter/Pi 运行超时再加 30 秒宽限期仍未进入终态时，读取状态会以条件追加方式写入 `failed` 终态与关联审计；跨线程/进程使用同一治理目录锁，`completed / failed / cancelled` 均为不可逆终态。`local` 没有外部 provider 超时，不套用该阈值。
- **queued 超时收敛**：`queued` 状态超过 `agent_run_queued_timeout_seconds`（缺省 600 秒）仍未开始执行时，读取状态会条件追加 `failed` 终态与关联审计（`error_type=StaleQueuedAgentRun`），避免排队 run 永久悬挂。

`GET /api/agent/runs`

- 返回当前用户的 run 列表（`limit` 1-100，缺省 20；可按 `conversation_id` 过滤，会话须归属当前用户）。

`POST /api/agent/runs/{run_id}/cancel`

- 仅 owner 可取消；`queued / starting / running` 可取消为 `cancelled`（不可逆终态），其他状态返回 409。
- **取消释放执行槽并终止 Hermes 子进程**：执行监督循环每 0.5 秒轮询 run 终态，观察到 `cancelled` 后置位 `cancel_event` 并立即返回、释放 worker 执行槽。显式声明 `cancel_event` 关键字的 executor（当前为 Hermes CLI/streaming 路径）收到置位后 `terminate()` 子进程并以取消错误码结束，其结果被状态守卫丢弃、不再写 failed 终态或审计；local/Dexter executor 不声明该关键字，仍在守护线程中自然收尾。

`POST /api/agent/runs/{run_id}/retry`

- 仅 owner 可重试；仅 `failed / cancelled` 终态可重试（生成新 `run_id`），其他状态返回 409。

`GET /api/agent/runs/{run_id}/events`（SSE）

- 以 `text/event-stream` 推送 run 状态快照，进入终态后结束。
- **keepalive 心跳**：快照无变化时每 15 秒发送一条 SSE 注释帧（`: keepalive`），防止空闲代理断开连接；EventSource 类解析器原生忽略注释帧，不影响事件契约。

工作台端点：`/api/agent/projects`、`/api/agent/projects/{id}/conversations` 等 workspace 端点与 agent 路由同挂载、同受 `MOSS_AGENT_ENABLED` 与 agent scope 鉴权（读 `agent:read`、写 `agent:write`）约束。项目/会话的创建、更新、归档、恢复现在写入 `agent_audit`（`result_kind` 前缀 `agent.workspace.`，如 `agent.workspace.project_created`），`result_meta` 只含 id 与变更字段名，不复制标题或消息正文；no-op 更新不写审计。

`GET /api/agent/models`：模型目录按 `(command, distro, home)` 键缓存 60 秒，采用 stale-while-revalidate——有缓存（即使过期）立即返回并在后台单飞刷新；完全无缓存时冷启动最多等待 3 秒 live discovery，超时回退到配置默认模型。目前只有 Hermes 有真实发现逻辑，local/Dexter/Pi 仅返回默认模型。

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

关键字路由（**`backend/app/agent/runtime/local_request_resolution.py`** 的 `_INTENT_PATTERNS`）：例如问题中含「组合概览」「资产规模」→ `portfolio_overview`；含「久期」「DV01」→ `duration_risk`。ASCII 关键词（`pnl`、`ftp`、`krd` 等）按词边界匹配，中文仍按子串。无法匹配时 intent 为 **`unknown`**，返回解释性答案而非 DuckDB 深度结果。

路由不再"首命中即返回"，而是收集全部命中后按以下规则收敛，收敛不了时返回 `semantic_status=clarification_required` 的澄清回答（不读取任何事实表、不调用 handler）：

- **特化优先**（`_INTENT_SPECIALIZATIONS`）：如「产品损益」同时命中 `product_pnl` 与 `pnl_summary` 时直接取 `product_pnl`；「风险张量」压制 `duration_risk`。
- **同族取序**（`_INTENT_FAMILIES`）：同一意图族内多命中沿用词表顺序；跨族多命中（如「损益和新闻」）先尝试用页面默认 intent 消歧，仍不唯一则澄清，`reason_code=multiple_intents`，候选放在 `intent_candidates`。
- **否定剔除**（`_INTENT_NEGATION_PATTERNS`）：「不要看损益，看新闻」中被否定的 `pnl_summary` 从候选移除后路由到 `news`；候选全部被否定则澄清，`reason_code=negated_intent_reference`。「类别」「差别」等含「别」字的普通词不会误判为否定。
- **相对日期澄清**（`_RELATIVE_DAY_PATTERNS`）：对结果绑定报告日的七个意图（`pnl_summary`、`pnl_bridge`、`product_pnl`、`portfolio_overview`、`risk_tensor`、`duration_risk`、`credit_exposure`），问题含「今日/今天/昨天/前天/上周X/today/yesterday」等明确相对日词、且 question/filters/context/page_context 中都没有 ISO 报告日时，不再静默取最新日期，而是澄清 `reason_code=relative_date_requires_explicit_report_date`。「最近/目前/当前」等模糊词以及 `market_data`、`news`、盘前/walk-forward 意图保持"最新可用"语义。

也可在请求的 **`context.intent`** 中显式指定 intent（需与后端路由约定一致）；显式 intent、显式 workflow、页面默认 intent 的优先级高于关键词收敛。

路由回归基线：`tests/fixtures/agent_intent_eval_set.v1.json`（106 条固定问法，含正例、近似反例、否定、多意图、歧义、相对日期、显式日期与页面默认）由 `tests/test_agent_intent_eval_set.py` 逐条回放，要求 100% 命中。

本体数值路由的币种口径：只有客户端**显式设置**了 `currency_basis` 才作为约束（显式 `CNX`/`USD` 仍在取数前被拒）；未显式设置时按 `CNY` 处理，服务端在 `pin_semantic_execution_request` 固化快照时会把有效口径写回 pinned 请求，保证下游绑定校验一致。`AgentQueryRequest.currency_basis` 的 schema 默认值 `CNX` 未改。

### 正式口径复用与元数据投影

`pnl_summary`、`duration_risk`、`pnl_bridge`、`risk_tensor`、`portfolio_overview`、`product_pnl` 六个 handler 复用对应正式 service 的完整 envelope（`pnl_service.pnl_overview_envelope`、`risk_tensor_service.risk_tensor_envelope`、`pnl_bridge_service.pnl_bridge_envelope`、`balance_analysis_service.balance_analysis_overview_envelope`、`product_category_pnl_service.product_category_pnl_envelope`），数值与治理元数据来自上游，不再由 Agent 自算。上游 `result_meta` 经 `agent_service._upstream_meta_projection` 以**显式白名单**投影到 Agent payload：治理版本串（`source_version / rule_version / cache_version / vendor_version / vendor_status / basis / fallback_mode`）必须由 handler 给出缺省值；日期与金额上下文字段仅在 handler 沿用上游口径时继承；`cache_key`、`data_built_at` 仅上游存在时透传；`formal_use_allowed` 取上游值与 Agent 自身 fail-closed 判定的**合取**，结构上不可能把上游 false 升级为 true；`quality_flag` 不继承，由各 handler 按自身降级规则判定。

- `portfolio_overview` 在复用正式 envelope 之外**保留** Agent 侧行级血缘完整性检查（`lineage_row_count / source_version_missing_count / rule_version_missing_count` 来自 `fetch_formal_overview`）：正式 balance 服务只用构建级血缘，这条是 Agent 比正式页更严的附加门槛，命中时 `formal_use_allowed=false`、`quality_flag=warning`，并出 `Governed Lineage Incomplete` 卡。
- `credit_exposure` 的数字仍由 `fetch_credit_summary` 计算，但正式资格与版本元数据改为 `bond_analytics_service.bond_analytics_credit_exposure_governance_meta(duckdb_path, governance_dir, report_date)`：要求存在该报告日已完成的 bond analytics 治理 run 且血缘可解析；缺失或解析失败时 fail-closed（`formal_use_allowed=false`、`quality_flag=warning`、`fallback_reason` 给出原因，意外异常只披露 `error_type`）。硬编码的 `sv_agent_credit_exposure` 已移除；这是有意的业务资格收紧，只建 DuckDB 表而不写治理 run 的环境将不再得到正式口径的信用敞口。

### Workflow（plan / execute 双模式）

- 金融 workflow：slash 命令 `/portfolio-review`、`/pnl-review`、`/risk-memo`、`/market-brief` 或 `context.workflow_id`。默认返回 **plan 卡**（`result_kind=agent.workflow.<id>`，`formal_use_allowed=false`）；`context.workflow_mode="execute"` 时按目录顺序执行映射 intents 并返回汇总。详见 `docs/agent_financial_workflows.md`。
- 研究 workflow：`/research-radar`、关键字「研究速读」「研究雷达」或 `context.workflow_id="research_radar_brief"`。默认同样返回 plan 卡；`context.workflow_mode="execute"` 时执行 `research_radar_brief` handler。显式 `context.intent="research_radar_brief"` 保持既有语义：直接执行简报（不经 plan 卡）。
- 所有 workflow 结果均为 `formal_use_allowed=false`，不新增写路径、不触发副作用。
- **统一报告日**：execute 模式下若请求没有显式报告日，第一个成功子步骤解析出的 `report_date` 会作为后续步骤的显式 `context.report_date`，聚合结果的 `filters_applied.workflow_pinned_report_date` 记录该日期；后续步骤在该日期无数据时由既有的失败路径显式反映，不会静默回退到各自的最新日期。
- **降级与失败分离**：`failed_intents` 只含异常/缺失结果的步骤，`degraded_intents` 含执行成功但 `quality_flag` 为 warning/stale 的步骤；顶层 `quality_flag` 规则为全部硬失败 → `error`，存在 failed 或 degraded → `warning`，否则 `ok`。memo 文案按两类分别列出。

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
- 动作 payload 必须内嵌 **`confirmation_scope.user_id`**（服务端签发时注入，`run_id` 可选）：scope 属于 payload，由同一 HMAC 保护，篡改 scope 即校验失败；签发用户与提交用户不一致 403。缺 `user_id` 的 token 一律按无效 token 拒绝（签发侧 fail-closed 拒发；旧的无 scope 兼容放行已移除，存量旧 token 在 15 分钟 TTL 内自然失效）。
- token secret 来源：`agent_action_token_secret`（settings，经 `MOSS_AGENT_ACTION_TOKEN_SECRET` 环境变量注入）；未配置时回退进程本地随机值，**跨进程校验会失败**（见「本地启用」第 5 条）。

---

## 安全边界

- **只读**：Agent MVP 设计为从已有 DuckDB / 治理链路读取并组装答案，不在浏览器端执行任意 SQL。
- **不执行客户端传来的 SQL**：前端与请求体均不应携带可执行 SQL 并由服务端直接执行（服务端工具链内部生成的审计字段 `sql_executed` 仅用于披露）。
- **不通过本接口触发 refresh / 写入任务**：驾驶舱 **`AgentPanel`** 仅展示建议动作 chip，不触发写入副作用。
- **审计全覆盖**：成功、失败、disabled、run 终态均写 `agent_audit`（唯一正式入口 `append_agent_audit`；run 终态为保证原子性与终态同锁追加，payload 契约一致）；失败记录只含异常类型，不含原始错误正文。Hermes/Dexter 的 provider 审计写入失败时 fail-closed（抛错、不返回应答），workspace 项目/会话生命周期操作同样写审计。
- **外发 prompt 预算**：Hermes 的 prompt 上下文按键优先级 JSON 序列化，超预算时整键丢弃（顺序见 `_PROMPT_CONTEXT_DROP_ORDER`）并在 prompt 末尾追加 `[context truncated: dropped keys ...]`，不再按字符硬截断；Dexter 送入 CLI argv 的完整 prompt 设总预算，超预算按优先级整键丢弃，被丢键通过 `filters_applied.prompt_context_dropped_keys` 披露，研究上下文预算为硬上限（裁剪后仍超预算则抛错，不再"仅告警继续"）。
- **Hermes transport 选择显式化**：`_select_hermes_transport(...)` 统一决定 sync CLI / bridge / streaming，配置的 transport 因请求字段（delta 回调、reasoning effort、显式 model）被覆盖时记录一条 INFO 日志说明原因。
- **bridge 授权字段**：配置了 `HERMES_BRIDGE_TOKEN` 时，health 响应缺少 `authorized` 字段视为不可用（fail-closed）；未配置 token 的旧兼容场景保持现状。
- **确认边界在服务端**：需确认的 suggested action 以服务端目录 + HMAC token 强制，客户端声明不再是控制边界（见上节）。
- **外部 CLI 信任边界**：`backend/app/agent/runtime/toolset_policy.py` 定义的工具集白名单（Hermes 仅限 `web`，Dexter 仅限 `evidence,query,research`）为**名称级过滤**，底层实际只读语义由外部 CLI 自行实现与保证。升级外部 Hermes/Dexter CLI 版本可能导致工具语义发生漂移或引入非预期写入行为，且白名单无法自动感知该类变更。因此，**在升级外部 CLI 前必须严格复核对应工具集（`web` / `evidence` / `query` / `research`）仍保持严格只读**。推荐的复核手段包括：
  1. **变更日志与代码审查**：检查外部 CLI 的发版说明（Release Notes）与代码变更，确认工具集实现未引入写操作、文件修改或未受控的网络写交互；
  2. **黑盒探测验证**：在隔离测试环境中对各工具集构造修改性/破坏性 prompt 探测（如试图写入文件、篡改数据或执行非授权命令），验证外部 CLI 具备严格的拒绝与只读防护表现。
- **禁用模式**：`MOSS_AGENT_ENABLED=false` 时 router 不注册，Agent URL 返回 404 且不进入 OpenAPI；路由级 503/audit 仅是显式挂载场景的二次防线。

---

## Disabled 模式（404 / 未注册）

前端应提示「Agent 当前未启用」，而不是当作 **`AgentEnvelope`** 解析。

---

## Agent run 流压缩（强制周期运维任务）

用途：控制 `data/governance/` 目录下 `agent_run.jsonl`、`agent_run_dispatch.jsonl` 与 `agent_run_delta.jsonl` 三条治理流的文件体积。`compact_agent_run_streams` 任务**未接入任何内部自动调度器**（代码设计为 intentionally not wired），三条流会随 run 运行无限追加增长。**若不周期性执行压缩，读路径（如 `GET /api/agent/runs` 用户列表查询、run 状态加载与治理分析）将被迫做全量扫描与反序列化，导致查询性能严重退化与接口响应延迟上升**。因此必须由外部运维系统强制定期触发。

- **执行频率要求**：
  1. **生产/活跃环境**：**强制每日在业务低峰期（如凌晨）执行一次**（可通过外部 cron、Windows 计划任务或 CI/CD 运维定时作业调度）；
  2. **开发/测试环境**：建议至少**每周执行一次**；
  3. 保留窗口默认 7 天（可通过 `MOSS_AGENT_RUN_STREAM_RETENTION_DAYS` 或 settings `agent_run_stream_retention_days` 覆盖配置），终态且最后写入超过保留窗口的 run 仅在 `agent_run` 保留最后终态快照，`agent_run_dispatch` 与 `agent_run_delta` 对应明细行被精简，删除行追加归档至同目录 `<stream>.archive.jsonl`，不丢数据。
- **触发方式**（真实模块路径 `backend/app/tasks/agent_run_stream_compaction.py`）：
  1. **直接脚本调用（推荐用于外部 cron/计划任务）**：
     `python -c "from backend.app.governance.settings import get_settings; from backend.app.tasks.agent_run_stream_compaction import compact_agent_run_streams; print(compact_agent_run_streams(settings=get_settings()))"`
  2. **Broker 异步派发**：
     经 Dramatiq broker 派发 actor `compact_agent_run_streams`（已由 `backend/app/tasks/agent_run_stream_compaction.py` 的 `compact_agent_run_streams_task` 注册，`worker_bootstrap` 自动加载）。
- **验证**：
  1. 检查命令输出/日志中的 `runs_compacted` 与 `agent_run_archived` / `agent_run_dispatch_archived` / `agent_run_delta_archived` 计数；
  2. 确认 `agent_run_compaction.jsonl` 追加了本次压缩统计事件（无归档产生时不冗余写治理流）；
  3. 抽查任一已被压缩的旧 run 执行 `GET /api/agent/runs/{run_id}`，验证仍能正常返回其终态快照。
- **安全性与锁机制**：压缩幂等可重跑；执行期间持有 `AGENT_RUN_TRANSITION_FILE_LOCK` 与治理仓库批次锁，进行中的 run 写入会短暂等待；归档文件只增不删，如需彻底清理由治理流程另行决定。`agent_run_dispatch` 新增的 `phase` 字段不影响压缩逻辑（按 `run_id` 整行归档）。

## 故障排查

| 现象 | 可能原因 | 建议 |
|------|-----------|------|
| HTTP 404，OpenAPI 无 `/api/agent*` | `MOSS_AGENT_ENABLED` 未打开 | 这是当前默认发布边界；只有取得明确试点授权后才可设为 `true` 并重启后端 |
| HTTP 503，正文非 disabled JSON | 运行时错误（如 Hermes 超时）；参见 `RuntimeError` 路径 | 查后端日志、`MOSS_AGENT_PROVIDER` 与 Hermes 配置 |
| 返回「无报告日期」类 **ValueError** | 某仓库无可用 `report_date` | 确认 DuckDB 批次与日期列表接口 |
| `result_kind` 为 **`agent.unknown`** | 问题未匹配任一关键字且未指定 `context.intent` | 调整提问措辞或显式 intent |
| **`quality_flag` 为 stale / warning** | 数据陈旧或治理降级 | 对照 `result_meta` 与 evidence，勿当作正式发布的唯一依据 |
| run 长期停在 `queued` 后变 `failed`（`StaleQueuedAgentRun`） | worker 未消费或排队超过 `agent_run_queued_timeout_seconds`（缺省 600 秒） | 检查 worker 进程/心跳；确需更长排队时间时调大该配置 |
| 确认 suggested action 返回 403（`confirmation token`） | token 缺失/过期（15 分钟）/与动作不匹配/payload 缺 `confirmation_scope.user_id`（含收紧前签发的旧无 scope token）；或多进程部署未配置统一 `MOSS_AGENT_ACTION_TOKEN_SECRET` | 重新获取动作与 token；多进程部署为 API 与 worker 配置同一 secret 并重启 |
| bridge 模式 Hermes 持续降级，日志出现 `Hermes bridge at ... rejects this process's token` | 后端曾非优雅退出（kill -9/崩溃），上一进程的孤儿 bridge 仍占用端口并持旧一次性 token；新进程令牌不匹配被 403 | 按 bridge 端口找到孤儿进程并停掉（正常重启已由 lifespan 自动关停托管 bridge）；长期自管的外部 bridge 应配置固定 `HERMES_BRIDGE_TOKEN` 供各后端进程共用 |
| 配置了 bridge token 后 Hermes 一直走降级，health 可达 | bridge 版本过旧，health 响应没有 `authorized` 字段，现按 fail-closed 视为不可用 | 升级 bridge 到会回传 `authorized` 的版本，或暂时移除 token 配置回到旧兼容模式（不推荐） |
| 生产环境 `/query` 或 `/runs` 返回 503/403，日志提到 `MOSS_AGENT_ACTION_TOKEN_SECRET` | `environment=production` 且未配置 token secret，签发/校验 fail-closed | 为 API 与 worker 配置同一 `MOSS_AGENT_ACTION_TOKEN_SECRET` 并重启 |
| provider 返回 503 且日志为 `audit append failed`（`error_type` 为治理仓库异常） | provider 审计写入失败，按 fail-closed 不返回未留痕应答 | 检查治理目录可写性与锁占用；修复后重试请求 |
| 回答变成澄清（`agent.ontology_clarification`），`reason_code` 为 `multiple_intents` / `negated_intent_reference` / `relative_date_requires_explicit_report_date` | 问题同时命中多个不同族意图、候选被否定、或含「今天/昨天」等相对日词但没有明确报告日 | 一次只问一类分析、明确要看的对象，或给出 `YYYY-MM-DD` 报告日 |
| Dexter 回答的 `filters_applied.prompt_context_dropped_keys` 非空 | 送入 CLI 的 prompt 超总预算，低优先级上下文键被整体丢弃 | 精简 `page_context`/`context`，或减少同时选中的行 |

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
