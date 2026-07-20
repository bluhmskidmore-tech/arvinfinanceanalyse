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
4. 确认 `config/macro_decision_observation_keys.json` 随包分发（macro toolkit `decision_summary` 懒加载依赖）

## Docker Compose 的 DuckDB 进程契约

- API 是启动期存储迁移的唯一 owner；worker 设置
  `MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=1`，并等待 API healthcheck 通过后再启动，避免与 API 并发执行迁移或在迁移完成前消费积压任务。
- Dramatiq 固定为一个 worker 进程；同一进程内可保留线程并发，受治理的物化入口继续使用现有按数据库路径生成的 writer lock。
- API 与 worker 仍是两个操作系统进程。短暂的读写重叠仍可能使 DuckDB 暂时不可用；本轮覆盖的 source preview 读接口和 PnL 读路径会返回 HTTP 503，不会返回未处理的 500，也不会把 source preview 失败伪装成空数据和 `quality_flag=ok`。
- 这是开发栈的安全约束，不代表仓库内所有直接 DuckDB 连接已经全局协调。若要彻底消除运行期重叠，需要后续选择单一数据库 owner 进程、发布只读快照，或实现全仓跨进程连接门闩。
