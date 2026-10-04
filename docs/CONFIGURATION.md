# CONFIGURATION

## 配置来源

当前仓库已验证的配置来源主要有五类：

1. `backend/app/governance/settings.py`
2. `config/.env` / `config/.env.example`
3. 根目录 `.env`（若存在）
4. `frontend/.env.example`
5. `scripts/dev-env.ps1` 与 `docker-compose.yml`

## 后端设置加载方式

`backend/app/governance/settings.py` 使用 `pydantic-settings`，并声明：

- `env_prefix="MOSS_"`
- `env_file=(config/.env, .env)`

这意味着：

- 优先使用环境变量和 `.env` 文件。
- 后端配置键默认走 `MOSS_*` 前缀。
- 相对路径按仓库根目录解析，而不是按当前 shell 工作目录解析。

## 核心环境变量

### 存储与运行时

| 变量 | 作用 | 默认/示例来源 |
| --- | --- | --- |
| `MOSS_ENVIRONMENT` | 环境名 | `development` |
| `MOSS_POSTGRES_DSN` | Postgres 连接串 | `config/.env.example` |
| `MOSS_GOVERNANCE_SQL_DSN` | governance SQL DSN | 若为空，回退到 `MOSS_POSTGRES_DSN` |
| `MOSS_REDIS_DSN` | Redis 连接串 | `redis://localhost:6379/0` |
| `MOSS_DUCKDB_PATH` | DuckDB 文件路径 | `data/moss.duckdb` |
| `MOSS_GOVERNANCE_PATH` | governance 目录 | `data/governance` |
| `MOSS_DATA_INPUT_ROOT` | 原始输入根目录 | 默认解析到 `data_input` |

### 对象存储

| 变量 | 作用 |
| --- | --- |
| `MOSS_OBJECT_STORE_MODE` | 本地或对象存储模式 |
| `MOSS_LOCAL_ARCHIVE_PATH` | 本地 archive 路径 |
| `MOSS_MINIO_ENDPOINT` | MinIO / S3 endpoint |
| `MOSS_MINIO_ACCESS_KEY` | 访问密钥 |
| `MOSS_MINIO_SECRET_KEY` | 密钥 |
| `MOSS_MINIO_BUCKET` | bucket 名称 |

### 外部数据与行情

| 变量 | 作用 |
| --- | --- |
| `MOSS_CHOICE_USERNAME` / `MOSS_CHOICE_PASSWORD` | Choice 账号 |
| `MOSS_CHOICE_EMQUANT_PARENT` | Choice 进程/父进程设置 |
| `MOSS_CHOICE_START_OPTIONS` | Choice 启动选项 |
| `MOSS_CHOICE_REQUEST_OPTIONS` | Choice 请求选项 |
| `MOSS_CHOICE_MACRO_CATALOG_FILE` | Choice 宏观目录文件 |
| `MOSS_CHOICE_MACRO_COMMANDS_FILE` | Choice 宏观命令文件 |
| `MOSS_CHOICE_NEWS_TOPICS_FILE` | Choice 新闻主题文件 |
| `MOSS_TUSHARE_TOKEN` | Tushare token |
| `MOSS_FX_OFFICIAL_SOURCE_PATH` | 官方 FX 源路径 |
| `MOSS_FX_MID_CSV_PATH` | FX 中间价 CSV 路径 |

### 业务相关设置

| 变量 | 作用 |
| --- | --- |
| `MOSS_PRODUCT_CATEGORY_SOURCE_DIR` | 产品分类损益源目录，默认指向 `data_input/pnl_总账对账-日均` |
| `MOSS_FTP_RATE_PCT` | FTP 利率配置 |
| `MOSS_FORMAL_PNL_ENABLED` | formal PnL 开关 |
| `MOSS_FORMAL_PNL_SCOPE_JSON` | formal PnL scope |
| `MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS` | 为 `true`（默认）时 `/api/pnl/by-business-ytd` 优先用 `fact_formal_pnl_fi` + `fact_nonstd_pnl_bridge` 累计；为 `false` 时用刷新包 + V1 兼容变换 |

## 路径解析规则

`backend/app/governance/settings.py` 中几条容易踩坑的规则：

- `config/.env` 和根 `.env` 都会被读取。
- 相对路径会被解析成仓库根路径下的绝对路径。
- 如果 `tmp-governance/pgdev/data` 存在，而 `MOSS_POSTGRES_DSN` 仍是默认 `localhost:5432`，设置层会自动把它切到 `127.0.0.1:55432`。
- `MOSS_GOVERNANCE_SQL_DSN` 如果不填，会自动继承 `MOSS_POSTGRES_DSN`。
- `MOSS_DATA_INPUT_ROOT` 未显式设置时，会优先尝试 legacy `RAW_FILES_DIR`，再尝试 `data_warehouse/raw_files`，最后回落到仓库内 `data_input/`。

显式指定 `MOSS_DATA_INPUT_ROOT` 或非空 `RAW_FILES_DIR` 后，产品类别输入和官方汇率来源缺失会报错，不再读取旧仓库副本；缺失的指定汇率也不会转向供应商取数。仅保留默认输入根配合显式产品子目录的原有开发兼容。

## 本地开发默认值

`scripts/dev-env.ps1` 与 `scripts/dev_postgres_cluster.py` 共同选择本地默认值；以下存储路径仅在没有明确配置时适用：

- `MOSS_POSTGRES_DSN=postgresql://moss:moss@127.0.0.1:55432/moss`
- `MOSS_GOVERNANCE_SQL_DSN` 同上
- `MOSS_REDIS_DSN=redis://127.0.0.1:6379/11`，由现有开发环境辅助脚本选择
- `MOSS_DUCKDB_PATH=<repo>/data/moss.duckdb`
- `MOSS_GOVERNANCE_PATH=<repo>/data/governance`
- `MOSS_LOCAL_ARCHIVE_PATH=<repo>/data/archive`
- `MOSS_MINIO_ENDPOINT=localhost:9000`
- `MOSS_MINIO_BUCKET=moss-artifacts`

上述连接和运行模式由本地开发入口选择。存储路径则保留明确配置：`MOSS_DUCKDB_PATH`、`MOSS_GOVERNANCE_PATH`、`MOSS_DATA_INPUT_ROOT`、`MOSS_LOCAL_ARCHIVE_PATH` 以及两类发布根目录，按当前进程环境、根 `.env`、`config/.env` 的顺序取值，相对路径仍以仓库根目录为基准。未配置的路径继续使用现有仓库或运行目录默认值。修改这些变量不会自动搬迁已有文件；所有读写进程必须在协调后的切换窗口使用一致配置。

原生 `dev-api.ps1` 强制启用 `MOSS_LOCAL_ONLY_API=1`，并核对实际 Settings。该单机策略要求回环监听和本机请求来源，拒绝转发身份头；明确关闭或非法值会中止原生启动。普通 development/Compose 默认不启用此策略，生产启动限制保持原约定。Agent 开发范围绕过只在原有合法本机链路中保留，不构成多人身份认证。

2026 年 10 月 4 日本机已切换以下五个活跃存储路径，后续原始输入应放入新的输入目录。余额发布根继续沿用原配置。

| 配置项 | 本机实际路径 |
| --- | --- |
| `MOSS_DUCKDB_PATH` | `D:/MOSS-data/moss.duckdb` |
| `MOSS_GOVERNANCE_PATH` | `D:/MOSS-data/governance` |
| `MOSS_LOCAL_ARCHIVE_PATH` | `D:/MOSS-data/archive` |
| `MOSS_DATA_INPUT_ROOT` | `D:/MOSS-data/data_input` |
| `MOSS_FINANCIAL_PUBLICATION_ROOT` | `D:/MOSS-data/publications/pnl-by-business` |

旧副本位于 `F:/MOSS-recovery/repository-maintenance-20261004`；历史归档身份由映射解析，历史备份回执保持原文。新目录已恢复运行后，不得直接切回旧副本：应先停写并核对新增数据和队列，再执行恢复。本次整理方案（执行证据仅保存在本地）记录实际范围与未迁移目录。

### 归档目录外置

历史来源清单、快照和来源版本保持原样。仅复制归档再改 `MOSS_LOCAL_ARCHIVE_PATH` 不足以完成迁移，因为历史记录包含绝对路径。当前读取链支持归档根目录中的 `.moss-archive-relocations.json` 映射，目标限定在该根目录内，按记录的 SHA256 校验读取内容。需要映射的历史路径缺少记录、目标丢失、链接逸出或内容不符时会报错，不回读旧归档或以其他输入掩盖错误。原本位于当前归档根目录内的文件不需要迁移映射。

映射路径的内容校验也会在 PnL 缓存指纹读取时执行，缓存命中不能省略这次完整文件校验。实际迁移前，应按代表性的归档大小与数量测量读取耗时；小样本演练不能证明大规模归档的性能。未迁移的根目录内普通文件继续沿用原读取方式。

[归档迁移工具](../scripts/archive_storage_migration.py)默认只生成迁移计划。`--write-sample` 仅允许有明确归属标记的系统临时目录样本；正式复制使用 `--apply-maintenance`，同时传入 `--repo-root`、现有维护流程的 `--owner-token` 和 `--offline-receipt`。正式入口要求仓库外的空目标，绑定本次维护与本地停写证据，并在发布映射前复核完整源、目标集合和内容。两种入口都只复制，不删除源文件；正式入口不负责停止进程，也不负责切换配置，停写声明必须来自实际排空结果。

实际业务迁移仍须停止相关写入，核对待执行、延迟和未确认的队列消息，验证恢复点，并保护目标目录与映射文件权限。部分任务消息含旧数据库绝对路径，不能带着这些消息直接切换后恢复 worker。映射中的哈希用于内容一致性，不能替代受信任的生成过程或访问控制。

本批支持同一操作系统内的目录外置。Windows 与 Linux 的历史绝对路径语义不同，跨系统的历史身份会被拒绝；跨系统搬迁历史业务数据还需统一文件名、目录片段和分类规则后另行验证。跨平台开发入口可以使用各平台自己的合成样本，这不代表历史业务数据已经支持跨系统迁移。

## 前端配置

前端环境变量主要来自 `frontend/.env.example` 和 `frontend/vite.config.ts`：

| 变量 | 作用 |
| --- | --- |
| `VITE_DATA_SOURCE` | 前端数据源模式 |
| `VITE_API_BASE_URL` | API 基地址；为空时走 Vite proxy |
| `VITE_JOB_POLL_INTERVAL_MS` | 轮询间隔 |
| `VITE_JOB_POLL_MAX_ATTEMPTS` | 最大轮询次数 |
| `MOSS_VITE_API_PROXY` | Vite proxy 目标地址，默认 `http://127.0.0.1:7888` |

`frontend/vite.config.ts` 已固定：

- 开发端口：`5888`
- 预览端口：`5888`
- `/api`、`/ui`、`/health` 会代理到后端

## Docker Compose 配置面

`docker-compose.yml` 不再写死任何凭据。以下宿主机环境变量在 `docker compose up` 前**必填**（compose 文件用 `${VAR:?...}` 声明，缺失时直接拒绝启动）：

- `MOSS_POSTGRES_PASSWORD`：Postgres 密码，同时注入 `postgres` 服务的 `POSTGRES_PASSWORD` 和 `api`/`worker` 的 DSN
- `MOSS_MINIO_ROOT_USER` / `MOSS_MINIO_ROOT_PASSWORD`：MinIO root 凭据，同时作为 `api`/`worker` 的 `MOSS_MINIO_ACCESS_KEY` / `MOSS_MINIO_SECRET_KEY`

可选覆盖（有默认值）：`MOSS_POSTGRES_USER`（默认 `moss`）、`MOSS_POSTGRES_DB`（默认 `moss`），以及宿主机端口映射 `MOSS_POSTGRES_PORT`、`MOSS_REDIS_PORT`、`MOSS_MINIO_PORT`、`MOSS_MINIO_CONSOLE_PORT`、`MOSS_FRONTEND_PORT`。

据此，`api` / `worker` 容器内得到的配置为：

- `MOSS_POSTGRES_DSN=postgresql://${MOSS_POSTGRES_USER}:${MOSS_POSTGRES_PASSWORD}@postgres:5432/${MOSS_POSTGRES_DB}`
- `MOSS_REDIS_DSN=redis://redis:6379/0`
- `MOSS_DUCKDB_PATH=data/moss.duckdb`
- `MOSS_MINIO_ENDPOINT=minio:9000`
- `MOSS_MINIO_ACCESS_KEY=${MOSS_MINIO_ROOT_USER}`、`MOSS_MINIO_SECRET_KEY=${MOSS_MINIO_ROOT_PASSWORD}`
- `MOSS_MINIO_BUCKET=moss-artifacts`

注意 `api` 服务**没有** `ports:` 映射：`8000` 只是容器内端口，宿主机不能直接访问，前端容器通过 `MOSS_VITE_API_PROXY=http://api:8000` 在 compose 网络内代理到它。

也就是说，本地 PowerShell 流程和容器化流程使用的是两套地址基线：前者偏 `127.0.0.1`，后者偏服务名。
