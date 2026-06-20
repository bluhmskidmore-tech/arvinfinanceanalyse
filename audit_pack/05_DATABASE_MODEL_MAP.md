# 05 — 数据库模型与字段（Postgres ORM / 迁移）

> DuckDB **无** centralized SQLAlchemy 模型：表结构由 ingestion / materialization 脚本与文档约定；本节覆盖 **PostgreSQL + Pydantic 边界**。

## SQLAlchemy ORM（`backend/app/models/`）

### 共用

| 项 | 说明 |
|----|------|
| `Base` | `DeclarativeBase`（`models/base.py`）|

### `kpi_owner` (`KpiOwner`)

| 列 | Python 类型 / SQLAlchemy | 备注 |
|----|---------------------------|------|
| `owner_id` | `Integer` PK AI | |
| `owner_name`,`org_unit` | `Text` | |
| `person_name` | `Text` nullable | |
| `year` | `Integer` index | |
| `scope_type` | `Text` | |
| `scope_key_json` | `Text` nullable | JSON 字符串 |
| `is_active` | `Boolean` | |
| `created_at`,`updated_at` | `DateTime(timezone=True)` | |

对应 API schema：见 `backend/app/schemas/kpi.py`（及前端 **`kpiClient` Decimal-as-string** 约定）。

### `kpi_metric` (`KpiMetric`)

包含 `metric_code`、`owner_id` **FK → kpi_owner**、`year`、`major_category`、`metric_name`、`target_value` **`Numeric(18,6)`**、`score_weight` **`Numeric`**、枚举类文本 `scoring_rule_type`、`data_source_type`、`is_active`、时间戳。  
索引：`owner_id`、`year`。  
映射注意：`target_value` 等 ORM Python 注解为 `float | None`，实际列为 **Numeric** → 存在 **-float/Decimal** 语感混用。

### `kpi_metric_value` (`KpiMetricValue`)

`metric_id` **FK**、`as_of_date` **`Date`（索引）**、多列 `Numeric` 实绩/进度、`source` nullable、时间戳。

### 治理：`cache_build_run`、`cache_manifest`、`source_version_registry`、`rule_version_registry`（`governance.py`）

- 大量 **`Text`/JSON payload**、`cache_key` 索引、`report_date` 存 **字符串**而非 `Date`。  
- 用于 lineage / governance 运行时；与 `core_finance` 物化任务联动审计。

### `user_role_scope` (`UserRoleScope`)

ACL：`user_id`（索引）、`role`、`resource`、`action`、`scope_key/value`、`is_active`、时间戳。  
后端 `ensure_user_allowed` 读此表。

### `job_run_state` (`job_state.py`)

`run_id` **String PK**；状态、缓存键、report_date **`String`**、时间字段 **`String`**（非原生 datetime）。

---

## Alembic

路径：`backend/alembic/versions/`  

示例版本文件名（快照）：`baseline_job_run_state_governance_tables`、`add_kpi_tables`、`add_user_role_scope_table`、`add_indexes_governance_tables`、`add_launch_governance_lineage_columns`。  
环境与入口：`backend/alembic/env.py`、`backend/alembic.ini`。  
初始化 **另见**（如存在）：`backend/app/postgres_migrations.py`。

---

## Pydantic Schemas（`backend/app/schemas/`）

- **数量庞大**：bond、pnl、ledger、Executive、Cube、PnL Attribution 等各域 **独立文件**。  
- 金融金额大量 **`Decimal` + JSON 序列化 string**（与前端 `contracts.ts` **注释对齐**）。

---

## 「前端字段」对齐策略

正式页面通常路径：**API dict → Adapter / selector → formatter → 图表配置**。  
漂移热点：`ApiEnvelope`、`result_meta`、`_meta`、`vendor_status`、`Numeric` vs `number`。  
Golden / 文档：`tests/golden_samples/`、`docs/pnl/*`、`frontend/src/test/*`。

---

## 命名不一致风险（审计提问清单）

| 话题 | 说明 |
|------|------|
| `report_date` / `as_of_date` | 有的在 Query，有的在 path；Duck vs PG 语义 |
| Snake vs camel | 后端多为 snake_case；极少数 legacy JSON |
| WAN / YUAN / 亿元 | Formatter 分层；`ADB`/`balance` 文档多次强调 |

---

## 说明：缺失目录

快照要求中的 `backend/app/db/**`、`backend/app/utils/**` **当前仓库未发现**对应包目录（若以其他名称存在可自行补充后续审计轮次）。
