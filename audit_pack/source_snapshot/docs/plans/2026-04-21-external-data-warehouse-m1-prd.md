# External Data Warehouse — M1 PRD（简版）

## 背景与目标

在 **D1–D6 决议**（见 `.omx/specs/deep-interview-external-data-warehouse-decisions.md`）约束下，M1 交付 **最小可工作骨架**：本地 **raw zone** 落盘约定、DuckDB **`external_data_catalog`** 表与仓库、只读 **HTTP 目录 API**、Tushare **adapter scaffold**（不实作真实 API），以及配套测试与本文档。  
**不**做 Choice macro 真迁、**不**改既有 macro/news/yield/FX 写入链路与老表 schema。

## M1 做了什么

| 能力 | 说明 |
|------|------|
| Raw zone | `RawZoneRepository`：`data/raw/{vendor}/{ingest_batch_id}/{filename}`，路径分量经 `_safe_component`；同路径同内容幂等，内容不同则拒绝覆盖。 |
| Catalog 表 | `external_data_catalog`（字段对齐 D3），经 schema registry + 版本化 migration **v13** 应用。 |
| Catalog 仓库 | `ExternalDataCatalogRepository`：`register`（按 `series_id` upsert）、`list_all`、`get_by_series_id`、`list_by_domain`；**不**访问 `phase1_macro_vendor_catalog`。 |
| HTTP | `GET /api/external-data/catalog`、`GET /api/external-data/catalog/{series_id}`、`GET /api/external-data/catalog/by-domain/{domain}`。 |
| Tushare | `register_to_catalog`、`fetch_macro_snapshot_skeleton`（fixture）；网络拉数仍为后续工作。 |

## 决议对齐（摘要）

- **D1**：新建 `data/raw/`，本期不用 MinIO；raw zone 由 **`RawZoneRepository`** 承担，与 `ObjectStoreRepository` 解耦。  
- **D3**：新建 `external_data_catalog` 为权威；与 `phase1_macro_vendor_catalog` 并存，M1 不改旧表。  
- **D4**：M1 仅 **catalog 薄 HTTP** + SQL 表；序列数据 HTTP 查询留 M2。  
- **D5/D6**：macro 真迁与 Tushare 全量接入 **不在 M1**；D6 仅作 M2 策略记录。

## 文件清单（M1 新增 / 小改）

**新增**

- `backend/app/schema_registry/duckdb/14_external_data_catalog.sql`
- `backend/app/repositories/raw_zone_repo.py`
- `backend/app/repositories/external_data_catalog_repo.py`
- `backend/app/schemas/external_data.py`
- `backend/app/services/external_data_service.py`
- `backend/app/api/routes/external_data.py`
- `tests/test_raw_zone_repo.py`
- `tests/test_external_data_catalog_repo.py`
- `tests/test_external_data_service.py`
- `tests/test_external_data_api.py`
- `docs/plans/2026-04-21-external-data-warehouse-m1-prd.md`

**小改**

- `backend/app/api/__init__.py`（注册路由）
- `backend/app/repositories/duckdb_migrations.py`（migration v13）
- `backend/app/schema_registry/duckdb/manifest.json`（注册 `14_external_data_catalog.sql`）
- `backend/app/repositories/tushare_adapter.py`（scaffold 方法）

## API 合同（M1）

- **`GET /api/external-data/catalog`**  
  - 200：JSON 数组，元素为 catalog 行（与 `ExternalDataCatalogEntry` 字段一致）。

- **`GET /api/external-data/catalog/{series_id}`**  
  - 200：单条对象。  
  - 404：`series_id` 不存在。

- **`GET /api/external-data/catalog/by-domain/{domain}`**  
  - `domain` ∈ `macro` | `news` | `yield_curve` | `fx` | `other`。  
  - 200：JSON 数组（该 domain 下全部 series）。

## 测试覆盖

- Raw zone：写入、读取、sha256、同内容幂等、不同内容拒绝、`healthcheck`。  
- Catalog repo：upsert、list、get、按 domain 过滤（内存 DuckDB）。  
- Service：mock repo 委托。  
- API：`TestClient` 三端点 + 404。

**验证命令（节选）**

```text
cd backend
ruff check app/repositories/external_data_catalog_repo.py app/repositories/raw_zone_repo.py ...
python -m pytest ../tests/test_raw_zone_repo.py ../tests/test_external_data_catalog_repo.py \
  ../tests/test_external_data_service.py ../tests/test_external_data_api.py
python -m pytest ../tests/test_duckdb_schema_registry_contract.py
```

## ⚠️ 文档 / 仓库事实注记

- 决议与任务稿中曾出现文件名 **`13_external_data_catalog.sql`**，但仓库中 **`13_news_warehouse.sql` 已占用** 序号；M1 DDL 落地为 **`14_external_data_catalog.sql`**，并在 `duckdb_migrations` 中注册为 **第 13 个版本化 migration**（`registry.register(13, ...)`）。若需与决议字面完全一致，需另行协调重命名策略（会牵动已有 news 迁移序号）。

## M2 入口建议（优先三项）

1. **Choice macro 真迁**：按 D6 影子表 + diff harness + 签核；浮点容差在 M2 PRD 冻结。  
2. **标准化表与 `vw_external_*`**：对齐 D2，并把现有只读消费逐步指到视图。  
3. **Tushare 真实接入**：在 `register_to_catalog` + raw zone + manifest 血缘上接通最小宏观日频 slice（仍不引入 Airflow/dbt 等新运行时）。

---

*本文档 ≤ 600 行约束；版本：M1 / 2026-04-21。*
