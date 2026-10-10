# decimal-backfill-2026-07-31 历史归档说明

## 归档性质

本目录为 **2026-07-31 Decimal 精度回填任务** 的历史静态快照。
目录内的所有脚本与归档测试均按归档时点原样保留，**仅作为历史审计与追溯证据，不保证可直接回放或独立运行**。

依据项目代码纪律与归档约定（见 `scripts/README.md`），禁止修改归档脚本代码。

---

## 已知失效导入清单

由于原顶层执行脚本与校验模块在归档时一并移入本目录，历史脚本中保留的以 `scripts.*` 形式的绝对导入在脱离顶层上下文后无法直接解析：

| 文件路径 | 行号 | 失效导入语句 | 缺失模块 / 原因 |
| --- | --- | --- | --- |
| `run_decimal_precision_backfill.py` | 2828 | `from scripts.verify_decimal_precision_backfill import verify_databases` | `scripts.verify_decimal_precision_backfill`（原模块已随归档移动至本目录 `verify_decimal_precision_backfill.py`） |
| `tests_archived/test_decimal_precision_backfill.py` | 15 | `from scripts import run_decimal_precision_backfill as runner` | `scripts.run_decimal_precision_backfill`（原模块已随归档移动至本目录 `run_decimal_precision_backfill.py`） |
| `tests_archived/test_decimal_precision_backfill.py` | 16 | `from scripts.verify_decimal_precision_backfill import verify_databases` | `scripts.verify_decimal_precision_backfill`（原模块已随归档移动至本目录 `verify_decimal_precision_backfill.py`） |
| `tests_archived/test_decimal_precision_backfill_verifier.py` | 11 | `import scripts.verify_decimal_precision_backfill as verifier_module` | `scripts.verify_decimal_precision_backfill`（原模块已随归档移动至本目录 `verify_decimal_precision_backfill.py`） |
| `tests_archived/test_decimal_precision_backfill_verifier.py` | 13 | `from scripts.verify_decimal_precision_backfill import (` | `scripts.verify_decimal_precision_backfill`（原模块已随归档移动至本目录 `verify_decimal_precision_backfill.py`） |

---

## 回放与替代路径

1. **历史任务状态**：本目录归档了 `2026-07-31` 单日 Decimal 精度回填的技术实现与隔离验证材料。归档不证明生产已执行；生产状态以 `docs/DECIMAL_PRECISION_2026-07-31_BACKFILL_RUNBOOK.md` 的 **BLOCKED** 门禁为准，不能据此发起生产回填。
2. **临时调试/复现方法**：如确需复现，应在隔离副本中显式恢复历史包路径并先验证导入；仅把本目录加入 `PYTHONPATH` 不会恢复失效的 `scripts.*` 模块名。本目录不提供可直接执行的生产入口。
3. **现行替代路径**：
   - 现行日常快照与余额物化任务已统一收敛至 `backend/app/tasks/snapshot_materialize.py` 与 `backend/app/tasks/balance_analysis_materialize.py`；
   - 官方金融计算中的精度规范以 `backend/app/core_finance/` 内的 Decimal 契约为准。
