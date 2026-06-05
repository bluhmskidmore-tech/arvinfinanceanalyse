# GETTING-STARTED

## 适用范围

这份文档聚焦“怎样把仓库跑起来并确认它活着”，不是完整业务操作手册。

## 先读什么

第一次进入仓库时，建议先读：

1. `AGENTS.md`
2. `docs/DOCUMENT_AUTHORITY.md`
3. `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`

如果要直接开始本地开发，再继续读本文。

## 环境基线

从当前仓库可验证到的技术基线看：

- 后端基于 Python `>=3.11`（`backend/pyproject.toml`）。
- 前端 CI 和 `docker-compose.yml` 使用 Node.js `22`。
- 本地开发脚本是 PowerShell（`scripts/dev-*.ps1`）。
- 容器化开发入口在 `docker-compose.yml`。

## 推荐启动方式

### 一键启动

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-up.ps1
```

这个脚本会按顺序执行：

1. `scripts/dev-postgres-up.ps1`
2. `scripts/dev-api.ps1`
3. `scripts/dev-worker.ps1`
4. `scripts/dev-frontend.ps1`
5. worker heartbeat smoke
6. API / frontend / lineage audit 检查

成功后可直接访问：

- Frontend: `http://127.0.0.1:5888`
- API health: `http://127.0.0.1:7888/health`
- Postgres: `postgresql://moss:moss@127.0.0.1:55432/moss`

## 分开启动

### 1. 本地 Postgres

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-postgres-up.ps1
```

### 2. API

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-api.ps1
```

`dev-api.ps1` 会先加载 `scripts/dev-env.ps1`，再以 `127.0.0.1:7888` 启动：

```text
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 7888
```

### 3. Worker

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-worker.ps1
```

Worker 启动命令来自脚本本体：

```text
python -m dramatiq backend.app.tasks.worker_bootstrap
```

### 4. Frontend

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-frontend.ps1
```

该脚本会在 `frontend/` 下自动安装依赖（若 `node_modules/` 不存在），然后执行 `npm run dev`。`frontend/vite.config.ts` 已固定开发端口为 `5888`。

## Docker Compose 方式

仓库同时提供容器化开发面：

```bash
docker compose up api worker frontend postgres redis minio
```

容器端口基线：

- API: `8000`
- Frontend: `5173`
- Postgres: `5432`
- Redis: `6379`
- MinIO API: `9000`
- MinIO Console: `9001`

`docker-compose.yml` 中的服务命令仍然是开发型命令：

- API: `pip install -e ./backend[dev] && python -m uvicorn backend.app.main:app ...`
- Worker: `pip install -e ./backend[dev] && python -m dramatiq backend.app.tasks.worker_bootstrap`
- Frontend: `npm run dev -- --host 0.0.0.0 --port 5173`

## 首次健康检查

建议至少验证以下探针：

### API

```bash
curl http://127.0.0.1:7888/health
```

### 典型业务读面

```bash
curl http://127.0.0.1:7888/api/bond-analytics/dates
```

### Frontend

在浏览器中打开：

- `http://127.0.0.1:5888`

## 不依赖脚本的手工方式

如果不想用 PowerShell 包装脚本，也可以按照仓库里已验证的命令单独执行：

### 后端

```bash
python -m pip install -e "./backend[dev]"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 7888
```

### Worker

```bash
python -m dramatiq backend.app.tasks.worker_bootstrap
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 建议的下一步

系统跑起来后，按这个顺序进入代码更稳妥：

1. `docs/ARCHITECTURE.md`
2. `docs/DEVELOPMENT.md`
3. `docs/TESTING.md`
4. 你要动的页面对应 `frontend/src/features/<domain>/`
5. 对应后端 `backend/app/api/routes/`、`services/`、`core_finance/`
