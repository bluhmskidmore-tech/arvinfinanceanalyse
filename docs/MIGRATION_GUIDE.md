# MOSS 存储迁移指南（Postgres + DuckDB）

本文说明如何新增与应用数据库 schema变更，并与仓库内的实现保持一致。

## 架构与约束（铁律）

- **调用方向**：`frontend → api → services → (repositories / core_finance / governance) → storage`。迁移脚本与 bootstrap 代码不得引入反向依赖或绕过该分层。
- **DuckDB 写入**：业务路径上 DuckDB 对 API 为只读；**业务写入**仅通过 `tasks`/worker。  
  **例外**：schema 迁移属于**基础设施**，可在 **API lifespan**、**worker 启动**（`storage_bootstrap`）时执行，与「只读 DuckDB」规则不冲突。
- **向后兼容**：对已有 DuckDB 文件升级时，DDL 必须幂等、不丢数据：优先 `CREATE TABLE IF NOT EXISTS`、`ALTER TABLE … ADD COLUMN IF NOT EXISTS`；避免无条件 `DROP`/`TRUNCATE` 生产数据。
- **真源**：DuckDB 的 baseline DDL 以 `backend/app/schema_registry/duckdb/*.sql`（`-- MOSS:STMT` 分片）为准；新增迁移时须从对应 `repository`/`task` 源文件**复制实际 SQL**，禁止凭记忆手写。

---

## Postgres：Alembic

### 环境

- 连接串由环境变量 **`MOSS_POSTGRES_DSN`** 提供（见 `backend/alembic/env.py`：`postgresql://` 会规范为 `postgresql+psycopg://`）。
- 配置文件：`backend/alembic.ini`，脚本目录：`backend/alembic/`。

### 创建新迁移（推荐 autogenerate）

在仓库根目录执行（工作目录为 `backend`，以便 `prepend_sys_path` 与 `alembic.ini` 一致）：

```bash
cd backend
alembic revision --autogenerate -m "short_description"
```

生成后**务必人工审阅** `backend/alembic/versions/` 下新文件：去掉误删、补上缺省、确认与 `backend/app/models/` 一致。

### 应用迁移

- **启动时自动**：`backend/app/storage_bootstrap.py` → `upgrade_postgres_schema_head()`（受 `MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS` 等标志影响，测试默认可能跳过）。
- **手动**：

```bash
cd backend
alembic upgrade head
```

（需已设置 `MOSS_POSTGRES_DSN`。）

### 回滚 Postgres

```bash
cd backend
alembic downgrade -1
```

回滚前请确认下游环境与数据可接受；生产环境应有独立变更流程。

---

## DuckDB：版本化 Schema Registry

### 组件

- **注册与元表**：`backend/app/repositories/duckdb_schema_registry.py`（`_schema_migrations`记录已应用版本）。
- **迁移列表**：`backend/app/repositories/duckdb_migrations.py`（`register_all` 中 `registry.register(version, description, fn)`）。
- **DDL 分片**：`backend/app/schema_registry/duckdb/*.sql`，语句之间用单独一行 `-- MOSS:STMT` 分隔；顺序见同目录 `manifest.json`（与 baseline 切片一致）。

### 创建新的 DuckDB 迁移（v12 及以后）

1. 在 **`backend/app/schema_registry/duckdb/`** 中新增或扩展 SQL 分片（保持 `-- MOSS:STMT` 约定），DDL 从相关 `ensure_*` / 任务代码**逐条拷贝**。
2. 在 **`duckdb_migrations.py`** 中：
   - 新增 `_vN_…(conn)`，内部调用 `_run_sql_slice(conn, "xx_your_slice.sql")` 或组合多个 slice；
   - 在 **`register_all`** 末尾追加一行 `registry.register(N, "…", _vN_…)`，**版本号全局递增、唯一**。
3. 更新/新增测试：契约指纹或 `tests/test_duckdb_schema_registry.py` 等，确保 baseline 数量与行为正确。

### 应用 DuckDB 迁移

- **启动时自动**：`upgrade_duckdb_schema_head()`（`backend/app/duckdb_schema_bootstrap.py`）→ `DuckDBSchemaRegistry.apply_pending()`。
- 业务代码中的 `ensure_*` 会委托 `apply_pending_migrations_on_connection(conn)`，在**同一连接**上补全未执行版本（含嵌套事务场景下的实现约定）。

### DuckDB「回滚」

当前**无**自动 down 迁移链；修复方式一般为**向前**追加新版本（`ADD COLUMN IF NOT EXISTS`、新表 `IF NOT EXISTS`）。若需收缩 schema，须单独设计数据迁移与发布流程。

---

## 与已删除手工 SQL 的说明

历史文件 **`sql/0001_bootstrap_governance.sql`**（若仍存在于旧分支）已由 **Postgres Alembic baseline**（如 `backend/alembic/versions/*_baseline_*.py`）替代；仓库中不应再依赖该路径。当前主线以 Alembic 与 DuckDB registry 为唯一 schema 来源。

---

## 发布前自检

- [ ] Postgres：`cd backend && alembic upgrade head` 在目标 DSN 上成功。
- [ ] DuckDB：新库与旧库上 `apply_pending` 均幂等、无报错。
- [ ] 全量测试：`pytest tests/`（或 `pytest tests/ -x` 快速排错）。
