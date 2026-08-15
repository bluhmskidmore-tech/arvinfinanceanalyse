# MOSS V3

MOSS V3 是一个以固定收益分析、经营分析和治理追踪为核心的业务系统仓库。根据 [AGENTS.md](AGENTS.md)，当前优先级是业务指标正确性、页面级闭环、traceability / validation，以及最小可审查改动。

这份 README 基于当前目录树、入口文件和各层 `AGENTS.md` 整理，目的是给新进入仓库的人一个可落地的起点，而不是替代已有的专项业务规范。

**首次进入仓库**：先按 [docs/ONBOARD_CHECKLIST.md](docs/ONBOARD_CHECKLIST.md) 走一遍（约 5～30 分钟，含启动与健康检查）。

## 建议阅读顺序

1. [AGENTS.md](AGENTS.md)
2. [docs/DOCUMENT_AUTHORITY.md](docs/DOCUMENT_AUTHORITY.md)
3. [docs/CURRENT_EFFECTIVE_ENTRYPOINT.md](docs/CURRENT_EFFECTIVE_ENTRYPOINT.md)
4. [docs/CURRENT_BOUNDARY_HANDOFF_2026-04-10.md](docs/CURRENT_BOUNDARY_HANDOFF_2026-04-10.md)
5. [docs/page_contracts.md](docs/page_contracts.md)（进入具体页面前再读）

## 系统形态

仓库遵循固定分层方向：

`frontend -> api -> services -> (repositories / core_finance / governance) -> storage`

关键约束：

- `backend/app/core_finance/` 是正式金融计算唯一入口。
- `backend/app/api/` 负责参数校验、**授权**、编排和响应映射。
- `backend/app/tasks/` 是 DuckDB / 物化写入入口。
- `frontend/` 负责消费结果和展示，不应补算正式金融指标。

关于「授权」的准确边界（**当前仓库有授权，没有认证**）：

- 授权（authorization）确实存在：`backend/app/security/auth_context.py::ensure_user_allowed` 做基于
  `resource`/`action`/`scope` 的 RBAC 判定，`backend/app/api/deps.py` 把它接进路由依赖。
- 认证（authentication）**不存在**：仓库里没有 API Key、Bearer/JWT、会话或网关令牌校验。身份取自
  `X-User-Id` / `X-User-Role` 请求头（且只有显式打开 `MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST` 才被信任）
  → `MOSS_USER_ID` / `MOSS_USER_ROLE` 环境变量 → 兜底常量 `anonymous` / `viewer`。
- `validate_auth_startup_guardrails()` 只在 `environment != "development"` 时生效；`environment` 默认值
  就是 `development`（`backend/app/governance/settings.py`），所以默认本地运行时全部守卫被跳过。
- 两种运行姿态，都不构成认证：
  - 信任开关关闭（默认）——请求头被忽略，所有请求共用同一个进程级身份（环境变量或
    `anonymous`/`viewer`），RBAC 实际上是在对一个固定身份判权，不区分调用方。
  - 信任开关打开（开发/测试常态，`scripts/backend_release_suite.py` 就会设 `=1`）——任何调用方
    都能用请求头自称任意 `user_id` 和 `role`，服务端不做任何校验。
- 不要把现有 RBAC 当成「已鉴权」，也不要在它之上做安全性判断或对外暴露。

## 仓库地图

- `backend/`: FastAPI 后端、服务编排、仓储访问、formal compute、worker 任务。
- `frontend/`: React + Vite 工作台前端和页面级特性目录。
- `docs/`: 边界、规范、计划、handoff 和专题说明。
- `tests/`: Python pytest 契约、边界、回归与 golden sample 测试。
- `scripts/`: 本地启动、发布门禁、数据物化和治理维护脚本。
- `config/`: `.env` 模板和外部源配置。
- `data_input/`: 原始输入文件目录。
- `data/`: DuckDB、governance、archive、runtime logs。
- `sample_data/`: 示例数据和 smoke 运行素材。

## 快速启动

### 推荐：Windows 本地一键启动

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-up.ps1
```

该脚本会启动本地 Postgres dev cluster、API、worker 和 frontend，并验证以下探针：

- `http://127.0.0.1:7888/health`
- `http://127.0.0.1:7888/api/bond-analytics/dates`
- `http://127.0.0.1:5888`

默认地址：

- Frontend: `http://127.0.0.1:5888`
- API: `http://127.0.0.1:7888`
- Postgres: `postgresql://moss:moss@127.0.0.1:55432/moss`

### 分开启动

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-postgres-up.ps1
powershell -ExecutionPolicy Bypass -File scripts/dev-api.ps1
powershell -ExecutionPolicy Bypass -File scripts/dev-worker.ps1
powershell -ExecutionPolicy Bypass -File scripts/dev-frontend.ps1
```

### Docker Compose

```bash
docker compose up api worker frontend postgres redis minio
```

`docker-compose.yml` 中的容器端口基线是：

- API: `8000`
- Frontend: `5173`
- Postgres: `5432`
- Redis: `6379`
- MinIO: `9000` / `9001`

## 常用验证

### 前端

```bash
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

### 后端

**先看解释器**：不要用裸 `python`。很多机器上 `python` 会被无关 venv 遮蔽（本机就解析到一个没装
pytest 的 agent venv）。最坏情况不是报错退出，而是解析到另一个装了 pytest 但依赖版本不同的环境，
给出一个与本仓库无关的绿灯。统一用仓库自己的 `.venv`：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\backend_release_suite.py
```

POSIX 下对应 `.venv/bin/python`；CI 里 `uv sync --frozen` 已把 venv 前置进 `PATH`，那里的裸 `python`
才是安全的。同一纪律见 `scripts/README.md` 与 `docs/GLOBAL_DATA_REFRESH_RUNBOOK.md`。

`python scripts/backend_release_suite.py` 是当前 repo-wide Phase 2 formal-compute mainline 的
canonical backend gate（这是门禁的**名字**，本机执行时按上面的形式加解释器前缀）。

## 文档索引

- [docs/architecture.md](docs/architecture.md): 目录树、分层边界、AGENTS 作用域；现有架构边界说明。
- [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md): 本地启动与首次检查。
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md): 开发约束、目录落点和改动路径。
- [docs/TESTING.md](docs/TESTING.md): 测试结构和验证命令。
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md): 环境变量、端口和配置来源。
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): repo 中可验证的运行/部署面。
- [docs/DOCUMENT_AUTHORITY.md](docs/DOCUMENT_AUTHORITY.md): 文档权威顺序。
