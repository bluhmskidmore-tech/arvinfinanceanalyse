# External Data Warehouse — M2a PRD（Tushare vendor → raw zone → catalog）

## 背景

在 M1（`docs/plans/2026-04-21-external-data-warehouse-m1-prd.md`）已具备 `RawZoneRepository`、`external_data_catalog` 与 Tushare adapter **scaffold** 的前提下，M2a 将 Tushare 宏观数据按决议 **D1/D3/D5** 贯通为可重复运行的 **vendor → raw zone → catalog → source manifest** 闭环。**不**建立 `std_external_*` 物理表（M2b），**不**建立 `vw_external_*` 视图（M2b），**不**做 Choice macro 真迁（M2c）。

## M2a 交付内容

| 组件 | 说明 |
|------|------|
| `tushare_adapter.VendorAdapter.fetch_macro_snapshot(series_id)` | 懒加载 `tushare`，校验 `MOSS_TUSHARE_TOKEN`，按 seed 路由调用 `pro.cn_cpi()` / `pro.cn_gdp()`，归一为 `{vendor_kind, series_id, fetched_at, rows[]}`；无 token/包不可导入时 `RuntimeError`。保留 `fetch_macro_snapshot_skeleton` 供离线测试。 |
| `tushare_catalog_seed.TUSHARE_M2A_SERIES` | 硬编码 M2a 系列清单（含 `raw_zone_path_template`）。 |
| `TushareMacroIngestService` | 拉数 → `archive_bytes` → `external_data_catalog.register`（`access_path` 为 M2b 占位 SQL）→ `SourceManifestRepository.add_many`。 |
| `tasks/tushare_macro_ingest.run_tushare_macro_ingest_once` | 对 DuckDB 跑 `apply_pending_migrations_on_connection` 后执行 `ingest_all_seed_series`；默认生成 `tushare-macro-{UTC紧凑时间}-{uuid8}` 批次 id。 |
| 测试 | `test_tushare_adapter_m2a.py`、`test_tushare_macro_ingest_service.py`、`test_tushare_macro_ingest_task.py`（Tushare API 一律 mock）。 |

## 与 M1 的衔接

- **raw zone 路径**仍满足 `data/raw/{vendor}/{ingest_batch_id}/{filename}`（与 `raw_zone_path_template` 一致）。
- **catalog** 仍用 `ExternalDataCatalogRepository.register`；`standardized_table` / `view_name` 继续指向 M2 将落地的标准名，**access_path** 在 M2a 仅为占位，提示 M2b 再接到 std 表。
- M1 的 `register_to_catalog`（skeleton 单条）未删除，与 M2a 种子系列并存于同一 `external_data_catalog` 表（以 `series_id` 为键 upsert）。

## Tushare 接入清单（M2a 种子）

| series_id | API | 频率 | 值字段归一化 |
|-----------|-----|------|----------------|
| `tushare.macro.cn_cpi.monthly` | `cn_cpi` | 月 | `nt_yoy` → `value`，`month` → `trade_date`（月首） |
| `tushare.macro.cn_gdp.quarterly` | `cn_gdp` | 季 | `gdp_yoy` → `value`，`quarter` → `trade_date`（季末） |

## API / 合同变化

- **无** 新增对外 HTTP 路由；catalog 消费方式仍为既有 `/api/external-data/catalog`（M1）。
- **内部** 新增可调用入口：`run_tushare_macro_ingest_once(ingest_batch_id: str | None = None) -> dict`（返回 `ingest_batch_id` 与 `results` 列表，每项含 `series_id`, `raw_zone_path`, `catalog_entry`, `manifest_record`）。

## 血缘（source manifest）

`SourceManifestRepository.add_many` 写入行包含：`vendor_name`, `source_family`（`tushare_macro`）, `source_version`（payload SHA256 短摘要前缀）, `ingest_batch_id`, `report_date`（取行内最新 `trade_date`）, `source_file`（raw 文件名）, `archived_path`（raw zone 绝对路径或项目相对落盘路径字符串）。

## 测试与验证

```text
cd backend
ruff check app/repositories/tushare_adapter.py app/repositories/tushare_catalog_seed.py ...
python -m pytest ../tests/test_tushare_adapter_m2a.py ../tests/test_tushare_macro_ingest_service.py ../tests/test_tushare_macro_ingest_task.py
```

- 不依赖真实 Tushare：adapter 层用 `sys.modules` 注入假 `tushare` 模块；ingest 用 stub `VendorAdapter`。
- 全量 `pytest` 中已知与 **caliber** 相关的 1 个失败为工作区遗留，M2a 不修改对应测试。

## 本地 smoke（诚实说明）

在已配置 `MOSS_TUSHARE_TOKEN`、已安装 `tushare`、且能访问 Tushare 网络时，可从 **仓库根** 执行：

```text
cd backend
python -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path('.').resolve().parent)); from backend.app.tasks.tushare_macro_ingest import run_tushare_macro_ingest_once; print(run_tushare_macro_ingest_once())"
```

若从 `backend` 为 cwd 且 `backend` 已在 `PYTHONPATH`，可简化为 `python -c "from backend.app.tasks.tushare_macro_ingest import run_tushare_macro_ingest_once; print(run_tushare_macro_ingest_once())"`。

- **无 token** 时会在 `fetch_macro_snapshot` 处抛出 `RuntimeError`，提示 `MOSS_TUSHARE_TOKEN` 未设置。
- **无包** 时同样 `RuntimeError`，提示无法导入 `tushare`。

**开发服务器端口** 仍以 `7888` 为准；本 task 不绑定 HTTP 端口。

## M2b 建议入口（下阶段）

1. 定义并落地 `std_external_macro_monthly` / `std_external_macro_quarterly`（或按 D2 统一为 `std_external_macro_daily` + 粒度列），自 raw JSON 可重复物化。  
2. 建立 `vw_external_*` 与 `access_path` 的正式 SQL 引用。  
3. 将 Tushare 与 Choice macro 消费路径在 catalog + diff 策略下对齐（D6 真迁另案）。

---

*版本：M2a / 2026-04-22；行数约束 ≤400 行。*
