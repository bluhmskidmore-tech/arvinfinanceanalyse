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

- API / worker 都先从 `backend/uv.lock` 导出冻结闭包（`uv export --frozen ... --extra dev`），
  再 `uv pip install --system --no-deps` 安装该闭包与 editable backend——容器内不做二次解析，
  装出的版本与 CI、与 OSV 扫描对象逐字一致
- Frontend 跑的是 `npm run dev`

Compose 只装 `[dev]`。`akshare` / `tushare` 在 `[vendor]` extra 里，因此 worker 容器**跑不了**
真实行情/资讯摄取任务（调用时报错，非静默降级）。需要摄取的部署把 compose 命令里的
`--extra dev` 改成 `--extra dev --extra vendor`。`WindPy` / `EmQuantAPI` 由 Wind / Choice 终端
捆绑分发，PyPI 无对应包，不在 lock 体系内。

这说明 `docker-compose.yml` 更接近“可复现开发环境”，而不是一个已经产品化的生产部署清单。

## 发布前门禁

当前仓库把 `scripts/backend_release_suite.py` 定义为 canonical backend gate。

**本机执行必须显式指定解释器**：不要用裸 `python`。开发机上 `python` 常被无关 venv 遮蔽——本机实测
解析到一个 agent 用的 venv，里面根本没有 pytest。更危险的情况是它解析到另一个**装了 pytest 但依赖
版本不同**的环境：命令不报错，跑出一片绿灯，而这个绿灯与本仓库的实际状态无关。

```powershell
.\.venv\Scripts\python.exe scripts\backend_release_suite.py
```

- POSIX 下对应 `.venv/bin/python scripts/backend_release_suite.py`。
- CI 里 `uv sync --frozen` 已把 venv 前置进 `PATH`/`VIRTUAL_ENV`，所以 `.github/workflows/ci.yml`
  里的裸 `python` 是安全的；本机没有这层保障。
- 同一纪律见 `scripts/README.md`（「本机 `python` 可能被无关 venv 遮蔽，故脚本从不直接调 `python`」）、
  [TESTING.md](TESTING.md) 与 [DOCUMENT_AUTHORITY.md](DOCUMENT_AUTHORITY.md)。
- 上面这条只影响**解释器前缀**，与本文「Docker Compose 栈」一节的 `uv sync --frozen` 依赖安装方式无关。

它会先校验 governance lineage，再执行一组有界后端测试。对于当前 repo-wide Phase 2 formal-compute mainline，这个门禁比随手跑一次全量 pytest 更接近仓库内约定的 release cutoff。

## CI 与部署的关系

`.github/workflows/ci.yml` 当前提供的是 CI，而不是生产发布流水线。它有 **10 个 job**
（2026-08-13 核对）：`backend`、`agent-eval-replay`、`backend-full-pytest`、`backend-lint`、
`mypy-ratchet`、`frontend`、`lint`、`api-contract`、`secrets`、`osv`。

也就是说，CI 覆盖面远不止「后端测试 + 前端测试 + 前端 lint」：还包含 Gitleaks 密钥扫描、
OSV 依赖漏洞扫描与对账、OpenAPI spectral 契约检查、Ruff 静默异常硬门禁、mypy 棘轮（当前
`continue-on-error`，观察模式）、定时/合入 main 的全量 pytest，以及 PR diff 触及口径源文件时
强制运行红线测试的 caliber path-trigger gate。逐 job 的触发条件与步骤见
[TESTING.md](TESTING.md) 的「CI」一节；判断当前真实门禁以 `.github/workflows/ci.yml` 为准。

仓库中没有在根层看到已落地的 Kubernetes、Terraform、Helm 或云厂商发布清单。因此更稳妥的理解是：

- CI 已明确存在
- 本地 / Compose 运行面已明确存在
- 生产部署流程若存在，至少不在当前仓库根层以同等显式方式维护

## 建议的交付理解

如果你的任务是“把仓库跑起来”，用 PowerShell 或 Compose 即可。

如果你的任务是“宣称可以发布”，至少应先完成：

1. 必要的本地或 CI 验证
2. `.\.venv\Scripts\python.exe scripts\backend_release_suite.py`（见上文「发布前门禁」：本机不要用裸 `python`）
3. 对当前边界文档的核对，而不是只看服务是否能启动
4. 确认 `config/macro_decision_observation_keys.json` 随包分发（macro toolkit `decision_summary` 懒加载依赖）

## Docker Compose 的 DuckDB 进程契约

- API 是启动期存储迁移的唯一 owner；worker 设置
  `MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=1`，并等待 API healthcheck 通过后再启动，避免与 API 并发执行迁移或在迁移完成前消费积压任务。
- Dramatiq 固定为一个 worker 进程；同一进程内可保留线程并发，受治理的物化入口继续使用现有按数据库路径生成的 writer lock。
- API 与 worker 仍是两个操作系统进程。短暂的读写重叠仍可能使 DuckDB 暂时不可用；本轮覆盖的 source preview 读接口和 PnL 读路径会返回 HTTP 503，不会返回未处理的 500，也不会把 source preview 失败伪装成空数据和 `quality_flag=ok`。
- 这是开发栈的安全约束，不代表仓库内所有直接 DuckDB 连接已经全局协调。若要彻底消除运行期重叠，需要后续选择单一数据库 owner 进程、发布只读快照，或实现全仓跨进程连接门闩。
