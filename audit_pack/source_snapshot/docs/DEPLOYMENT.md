# DEPLOYMENT

## 说明

这份文档只记录仓库里已经能直接验证到的运行/部署面，不臆测未在代码仓库中出现的生产发布系统。

## 已验证的运行面

当前仓库里有两类明确可执行的运行面：

1. Windows 本地原生开发栈（PowerShell）
2. Docker Compose 容器化开发栈

## Windows 原生开发栈

主入口脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-up.ps1
```

它会：

- 拉起本地 Postgres dev cluster
- 启动 API、worker、frontend
- 检查 API health、bond analytics dates 和前端首页
- 执行 governance lineage audit

对外端口：

- API: `7888`
- Frontend: `5888`
- Postgres: `55432`

如果只想拆分运行，也可以分别使用：

- `scripts/dev-postgres-up.ps1`
- `scripts/dev-api.ps1`
- `scripts/dev-worker.ps1`
- `scripts/dev-frontend.ps1`

## Docker Compose 栈

容器化入口：

```bash
docker compose up api worker frontend postgres redis minio
```

服务与端口：

| 服务 | 作用 | 端口 |
| --- | --- | --- |
| `api` | FastAPI 应用 | `8000` |
| `worker` | Dramatiq worker | 无独立外部 HTTP 端口 |
| `frontend` | Vite dev server | `5173` |
| `postgres` | 主数据库 | `5432` |
| `redis` | 队列/缓存 | `6379` |
| `minio` | 对象存储 | `9000`, `9001` |

需要注意，Compose 中使用的仍然是开发型命令：

- API / worker 都通过 `pip install -e ./backend[dev]` 安装 editable backend
- Frontend 跑的是 `npm run dev`

这说明 `docker-compose.yml` 更接近“可复现开发环境”，而不是一个已经产品化的生产部署清单。

## 发布前门禁

当前仓库把以下脚本定义为 canonical backend gate：

```bash
python scripts/backend_release_suite.py
```

它会先校验 governance lineage，再执行一组有界后端测试。对于当前 repo-wide Phase 2 formal-compute mainline，这个门禁比随手跑一次全量 pytest 更接近仓库内约定的 release cutoff。

## CI 与部署的关系

`.github/workflows/ci.yml` 当前提供的是 CI，而不是生产发布流水线：

- backend tests
- frontend tests
- frontend lint

仓库中没有在根层看到已落地的 Kubernetes、Terraform、Helm 或云厂商发布清单。因此更稳妥的理解是：

- CI 已明确存在
- 本地 / Compose 运行面已明确存在
- 生产部署流程若存在，至少不在当前仓库根层以同等显式方式维护

## 建议的交付理解

如果你的任务是“把仓库跑起来”，用 PowerShell 或 Compose 即可。

如果你的任务是“宣称可以发布”，至少应先完成：

1. 必要的本地或 CI 验证
2. `python scripts/backend_release_suite.py`
3. 对当前边界文档的核对，而不是只看服务是否能启动
