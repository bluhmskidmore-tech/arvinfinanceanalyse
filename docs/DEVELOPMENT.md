# DEVELOPMENT

## 目标

这份文档把顶层 `AGENTS.md`、`backend/app/AGENTS.md` 和 `tests/AGENTS.md` 中与日常开发直接相关的约束，收敛成一份工程操作说明。

## 全局工作方式

顶层 `AGENTS.md` 的工作重点可以浓缩为四句话：

- 一次只修一个页面或一个工作流。
- 先保证业务指标正确，再谈结构美观。
- 保持最小、可审查、可回滚改动。
- 如果度量口径有歧义，不要猜。

## 不要先动的地方

除非已经证明根因就在这里，否则不要主动改：

- 数据库 schema
- auth / permission framework
- queue / scheduler / cache base
- global SDK wrappers
- shared infra layers
- app-wide state architecture
- 不相关 backend services

## 目录落点

### 页面/前端改动

优先在以下目录找落点：

- 页面域：`frontend/src/features/<domain>/`
- 公共组件：`frontend/src/components/`
- 路由：`frontend/src/router/routes.tsx`
- API client：`frontend/src/api/`
- 前端测试：`frontend/src/test/`

### 后端接口改动

通常会穿过以下层级：

- 路由：`backend/app/api/routes/`
- schema：`backend/app/schemas/`
- service：`backend/app/services/`
- repository：`backend/app/repositories/`
- formal compute：`backend/app/core_finance/`
- task / 物化：`backend/app/tasks/`

### 配置改动

优先检查：

- `backend/app/governance/settings.py`
- `config/.env.example`
- `frontend/.env.example`
- `scripts/dev-env.ps1`
- `docker-compose.yml`

## 分层铁律

这些规则在顶层和 `backend/app/AGENTS.md` 中是一致的：

- 正式金融计算只放在 `backend/app/core_finance/`。
- API 层不承载正式公式。
- Frontend 不补算正式指标。
- DuckDB 在 API / service 读链路上保持只读。
- DuckDB 写入通过 `backend/app/tasks/` / worker 进入。

## 页面和指标的排查顺序

顶层 `AGENTS.md` 对业务显示逻辑给出了固定追踪链：

`API response -> adapter/transformer -> store/state -> selector/computed -> component -> chart/table`

改动任何显示型指标时，都要顺手确认：

- 单位是否一致：元 / 万元 / 亿元 / % / bp
- 精度和 rounding
- Decimal / float / string 序列化
- `null` / `0` / `undefined` / `NaN`
- 交易日 vs 自然日
- 日度 vs 月末 vs YTD
- `as_of_date` / fallback date / cached date
- 是否有 stale mock 或硬编码 fallback

## 哪些位置最值得先看

如果你接手一个页面问题，通常先按这个顺序读文件：

1. `frontend/src/router/routes.tsx`
2. `frontend/src/features/<domain>/`
3. `frontend/src/api/`
4. `backend/app/api/routes/<domain>.py`
5. `backend/app/services/<domain>_service.py`
6. `backend/app/core_finance/<domain>.py`
7. `tests/` 下对应契约或页面测试

## 当前默认边界

当前默认开发边界是 repo-wide `Phase 2` formal-compute mainline。对于 `backend/app/` 和 `tests/` 子树，以下链路默认在边界内：

- formal balance
- formal PnL
- formal FX
- formal yield curve
- PnL bridge
- risk tensor
- core bond-analytics formal read surfaces

这不等于仓库里每个页面、每个路由、每份历史计划都在当前主线里。

## 提交前的最小验证

顶层 `AGENTS.md` 要求：

- 改业务显示逻辑时，要补最小必要测试：formatter、selector/computed、adapter/transform。
- 跑当前任务最窄但真实的检查，不要只给口头判断。

常见组合：

- 前端页面改动：`npm run lint`、`npm run typecheck`、相关 Vitest。
- 后端接口/计算改动：目标 pytest + 必要时 `python scripts/backend_release_suite.py`。
- 文档或边界改动：相关文档契约测试。

## 文档和 authority

如果发现业务说明、计划材料和当前代码状态互相冲突，不按“最新文件 wins”处理。先回到：

1. `AGENTS.md`
2. `docs/DOCUMENT_AUTHORITY.md`
3. `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`

再决定哪份材料才是当前工作流真正应该遵守的边界。
