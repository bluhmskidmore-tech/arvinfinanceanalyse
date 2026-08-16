# backend/scripts/

backend 侧数据管线脚本目录：DuckDB 物化 bootstrap、历史回填、余额/口径诊断与口径审计工具。
逐脚本盘点见 `docs/plans/tech-debt-remediation/C5-scripts-inventory.md`（2026-08-12 基线：13 个 .py）。

## 运行方式

统一从仓库根以模块方式运行（保证 `backend.*` 包可导入）：

```powershell
cd F:/MOSS-V3
python -m backend.scripts.<script_name> [--args]
```

## 新脚本规范（强制）

新增任何 `*.py` 必须以 docstring 开头，且包含 `Lifecycle:` 行：

```python
"""一行说明：这个脚本做什么、影响哪个表/数据面。

Lifecycle: permanent        # 或 one-off；one-off 必须注明触发事件与完成条件
Verify: python -m pytest tests/test_xxx.py    # 推荐：给出验证命令
"""
```

- `Lifecycle: permanent`：常驻（可反复重跑的管线/审计入口，如 `bootstrap_data_pipeline.py`、`audit_caliber_violations.py`）。
- `Lifecycle: one-off`：一次性（绑定单一事故/探测/迁移，如 `fix_silent_exceptions.py`、`probe_choice_treasury_10y_history.py`）。完成后随清理批次移入 `archive/`。

## 边界纪律

- **`backend/app` 生产代码不得 import `backend.scripts.*`**（依赖方向必须是 scripts → app，不可反向）。
  现存两个反例是已登记的技术债，勿新增、勿模仿：
  - `backend.scripts.backfill_crisis_score_inputs` ← `backend/app/tasks/`（3 处）
  - `backend.scripts.backfill_cross_asset_macro_environment` ← `backend/app/tasks/macro_backfill.py`
  这类被生产依赖的逻辑应迁入 `backend/app/tasks/`，脚本仅保留 CLI 壳。
- 正式金融计算只能放 `backend/app/core_finance/`；本目录脚本只做编排、搬运与诊断，不得内联口径逻辑（口径漂移由 `audit_caliber_violations.py` / `caliber_violations_summary.py` 盯防）。

## DuckDB 访问纪律（禁止裸 `duckdb.connect`）

- **读**：使用 `backend/app/repositories/duckdb_repo.py::read_only_connection(path)`。
- **写**：委托 `backend/app/tasks/` 的物化任务（task write scope），不要在脚本里直连写库。
- 存量脚本中的裸连接是已登记技术债（C5 报告 §5.3），修复前不要复制其写法。

## 归档约定

- 目标目录：`backend/scripts/archive/`（可按主题分子目录）。
- `one-off` 目的达成或被替代（如 `backfill_formal_balance.py` 与 `batch_materialize_balance.py` 功能重叠，人工确认保留其一）后，经批准用 `git mv` 移入，配套测试同步处理，`pytest --collect-only` 验证无 import 断裂。

## 归档记录

- 2026-08-12（C5 批次 1）：`diagnose_adb_coverage.py`、`diagnose_balance_diff.py` 移入 `archive/adb-recon-2026-05/`；`fix_silent_exceptions.py`、`probe_choice_treasury_10y_history.py` 移入 `archive/one-off-repairs/`（均无配套测试）；守卫白名单同步移除并排除 archive/ 扫描。
