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
- `backend/app/api/` 负责参数校验、鉴权、编排和响应映射。
- `backend/app/tasks/` 是 DuckDB / 物化写入入口。
- `frontend/` 负责消费结果和展示，不应补算正式金融指标。

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

```bash
python -m pytest -q
python scripts/backend_release_suite.py
```

`python scripts/backend_release_suite.py` 是当前 repo-wide Phase 2 formal-compute mainline 的 canonical backend gate。

## 文档索引

- [docs/architecture.md](docs/architecture.md): 目录树、分层边界、AGENTS 作用域；现有架构边界说明。
- [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md): 本地启动与首次检查。
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md): 开发约束、目录落点和改动路径。
- [docs/TESTING.md](docs/TESTING.md): 测试结构和验证命令。
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md): 环境变量、端口和配置来源。
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): repo 中可验证的运行/部署面。
- [docs/DOCUMENT_AUTHORITY.md](docs/DOCUMENT_AUTHORITY.md): 文档权威顺序。
