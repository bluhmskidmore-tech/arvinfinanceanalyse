# DEVELOPMENT

## 目标

这份文档维护日常开发的目录落点和操作入口。项目规则统一在根 [AGENTS.md](../AGENTS.md)，路径规则分别在 [frontend/AGENTS.md](../frontend/AGENTS.md)、[backend/app/AGENTS.md](../backend/app/AGENTS.md) 和 [tests/AGENTS.md](../tests/AGENTS.md)；本文件通过引用使用这些规则。

## 全局工作方式

任务优先级与最小实施原则见 [AGENTS.md 的 Mission and scope](../AGENTS.md#mission-and-scope)，执行和交付见[工作和验证协议](../AGENTS.md#work-and-validation-protocol)。

## 锁定安装与源码预览

新 checkout 使用 Python 3.11、Node 22 和已有 `uv`。在仓库根目录按后端锁文件安装，再进入前端按 npm 锁文件安装：

```sh
uv sync --frozen --project backend --extra dev --python 3.11
cd frontend
npm ci
npm run dev:source
```

源码入口会核对并打印实际 Python 环境，默认使用兼容的 `backend/.venv`。解释器覆盖、数据模式、端口和退出方式统一见 [前端开发入口](../frontend/README.md#启动热更新)。此处安装步骤不启动 API、worker 或数据刷新任务。

## 容器开发入口

现有容器启动入口见 [README 的 Docker Compose](../README.md#docker-compose)，凭据、地址和端口参数见 [Docker Compose 配置面](CONFIGURATION.md#docker-compose-配置面)，配置文件是 [docker-compose.yml](../docker-compose.yml)。容器内 API 使用 `8000`，由容器前端代理，API 不发布宿主机端口；宿主机 `5890` 源码预览默认代理 `127.0.0.1:7888`，不能据此认为两条路径已经联通。

开发验收应显式绑定样本或合成数据，并为宿主源码预览提供可访问的隔离 API，再设置 `MOSS_VITE_API_PROXY`。现有 Compose 直接挂载工作区、默认读取 `data/moss.duckdb`，不是现成的隔离验收环境。源码入口的 Vite/HMR/合成 HTTP 测试只验证启动与代理机制，不能替代真实应用或 Compose 验收。

## 真实应用的隔离联通检查

`tests/test_dev_frontend_application_live.py` 显式启用后，复制当前前端源码和 Vite 配置到测试目录并核对字节，复用已安装依赖；真实 API 使用六行合成持仓快照与独立 SQLite 只读授权。测试关闭启动迁移、预热、Agent 和发布读取，不启动 worker 或刷新任务，再由真实浏览器核对债券、同业页面和 API 来源版本。结束时核对数据库指纹未变、子进程退出及端口释放。这项检查不证明生产数据、后台更新或 Compose 已验收。

先完成上面的锁定安装，并准备当前 Playwright 版本的浏览器。Windows 使用已选择的 Node 22，在仓库根目录执行：

```powershell
$env:MOSS_TEST_FULL_APP = "1"
.\backend\.venv\Scripts\python.exe -m pytest tests/test_dev_frontend_application_live.py -q `
  --basetemp=.codex-tmp/real-application-acceptance
Remove-Item Env:MOSS_TEST_FULL_APP
```

Linux 的同一检查用 `MOSS_TEST_FULL_APP=1 backend/.venv/bin/python -m pytest tests/test_dev_frontend_application_live.py -q --basetemp=.codex-tmp/real-application-acceptance`。隔离依赖需要位于测试目录时，可显式设置 `MOSS_TEST_VITE_DEPENDENCIES` 指向完整锁定安装的 `node_modules`；不要链接另一平台的原生依赖。未设置启用变量时用例会跳过，跳过不算通过。浏览器检查与其它前端验证串行运行。

## 不要先动的地方

数据库、权限、队列等共享基础边界见 [AGENTS.md 的 Protected boundaries](../AGENTS.md#protected-boundaries)，不在操作说明中重复列举。

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

### 任务产物

任务临时产物、本地报告和运行控制状态的落点及保护条件见 [AGENTS.md 的临时产物与结项清理](../AGENTS.md#临时产物与结项清理)。新任务复用该规则，旧目录按生产者、消费者和运行归属逐项核对，不因新增落点约定自动迁移。

## 分层铁律

分层与正式金融计算边界见根 [PRD §2.2](../prd-moss-agent-analytics-os.md#22-固定调用方向)，后端实施约束见 [backend/app/AGENTS.md](../backend/app/AGENTS.md#non-negotiable-constraints)。

## 页面和指标的排查顺序

受影响指标的证据要求见 [AGENTS.md 的 Business evidence](../AGENTS.md#business-evidence)；页面数据转换、日期、单位与空值的具体核对项见 [frontend/AGENTS.md 的 Affected metric verification](../frontend/AGENTS.md#affected-metric-verification)。按本次影响路径使用已有要求。

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

当前默认边界与局部授权规则见 [DOCUMENT_AUTHORITY.md 的阶段边界规则](DOCUMENT_AUTHORITY.md#阶段边界规则)，已生效的接口和兼容边界见 [Current Surface Boundaries](DOCUMENT_AUTHORITY.md#current-surface-boundaries)。本文件不另维护一份范围清单。

## 提交前的最小验证

检查范围遵循 [AGENTS.md 的默认开发闭环](../AGENTS.md#默认开发闭环)。前端的启动和显式检查选择见 [frontend/README.md](../frontend/README.md#运行局部检查)，后端测试命令与解释器要求见 [tests/CLAUDE.md](../tests/CLAUDE.md#verification)，正式后端发布门禁见 [DOCUMENT_AUTHORITY.md 的 Backend Canonical Gate](DOCUMENT_AUTHORITY.md#backend-canonical-gate)。局部检查与正式发布各自按原要求执行。

## 开发边界与债务止增

开始一个页面或工作流后，可以把允许改动的路径显式列出；默认只报告，
加 `--strict` 才阻断：

```powershell
.\.venv\Scripts\python.exe scripts\audit_worktree_scope.py `
  --allow frontend/src/features/<domain> `
  --allow tests/<target-test>.py `
  --strict
```

`npm run debt:audit` 除前端内联样式和 `api/client.ts` 外，也冻结了当前六个
高维护成本文件的行数上限。新增能力应进入对应域模块，不再扩大 MCP 主文件、
MCP 全量测试、共享 contracts、产品类别损益页面/模型和 PnL 总服务。

## 文档和 authority

如果发现业务说明、计划材料和当前代码状态互相冲突，不按“最新文件 wins”处理。先回到：

1. `AGENTS.md`
2. `docs/DOCUMENT_AUTHORITY.md`
3. `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`

再决定哪份材料才是当前工作流真正应该遵守的边界。
