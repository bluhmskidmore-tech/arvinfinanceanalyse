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

## 路径解析规则

`backend/app/governance/settings.py` 中几条容易踩坑的规则：

- `config/.env` 和根 `.env` 都会被读取。
- 相对路径会被解析成仓库根路径下的绝对路径。
- 如果 `tmp-governance/pgdev/data` 存在，而 `MOSS_POSTGRES_DSN` 仍是默认 `localhost:5432`，设置层会自动把它切到 `127.0.0.1:55432`。
- `MOSS_GOVERNANCE_SQL_DSN` 如果不填，会自动继承 `MOSS_POSTGRES_DSN`。
- `MOSS_DATA_INPUT_ROOT` 未显式设置时，会优先尝试 legacy `RAW_FILES_DIR`，再尝试 `data_warehouse/raw_files`，最后回落到仓库内 `data_input/`。

## 本地开发默认值

`scripts/dev-env.ps1` 会注入一套本地默认值：

- `MOSS_POSTGRES_DSN=postgresql://moss:moss@127.0.0.1:55432/moss`
- `MOSS_GOVERNANCE_SQL_DSN` 同上
- `MOSS_REDIS_DSN=redis://localhost:6379/0`
- `MOSS_DUCKDB_PATH=<repo>/data/moss.duckdb`
- `MOSS_GOVERNANCE_PATH=<repo>/data/governance`
- `MOSS_LOCAL_ARCHIVE_PATH=<repo>/data/archive`
- `MOSS_MINIO_ENDPOINT=localhost:9000`
- `MOSS_MINIO_BUCKET=moss-artifacts`

因此在本地 PowerShell 流程里，优先相信脚本注入值，而不是手写 shell 当前环境的残留值。

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

`docker-compose.yml` 为容器化开发显式设置了：

- `MOSS_POSTGRES_DSN=postgresql://moss:moss@postgres:5432/moss`
- `MOSS_REDIS_DSN=redis://redis:6379/0`
- `MOSS_DUCKDB_PATH=data/moss.duckdb`
- `MOSS_MINIO_ENDPOINT=minio:9000`
- `MOSS_MINIO_BUCKET=moss-artifacts`

也就是说，本地 PowerShell 流程和容器化流程使用的是两套地址基线：前者偏 `127.0.0.1`，后者偏服务名。
