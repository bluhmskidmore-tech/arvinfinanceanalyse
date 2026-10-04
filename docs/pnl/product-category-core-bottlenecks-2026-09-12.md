# 产品损益核心链路瓶颈修复与验证

本轮处理产品损益从原始文件、正式计算、物化结果到首页累计损益回退的完整链路。已确认的根因是同一账户匹配被重复扫描、任一刷新都会重建全部历史，以及读取回退依赖任务模块并重复应用手工调整。改动保留现有金融口径和接口，使用现有计算器、数据库事务及治理回执；没有新增数据库表、依赖、队列或全局缓存。

`core_finance/product_category_pnl.py` 在一次计算内建立账户匹配索引。索引保存原始行，保留原始累加顺序，不预先合并 Decimal 金额，避免改变舍入、重复匹配、重叠前缀和负号语义。51 个匹配测试及独立差分复核覆盖这些边界。

`tasks/product_category_pnl.py` 与 `tasks/product_category_refresh_state.py` 以年份为重建单位。来源内容及版本、有效调整、年度配置、计算实现和实际落库内容一致时，跳过解析、计算及产品损益数据写入。变化年份从原始文件重新解析，避免复用已按八位小数落库、且已应用调整的 canonical 金额。历史修订、调整跨年迁移及来源删除均纳入影响年份；无有效来源仍失败并保留原结果。无变化刷新仍校验来源和结果，并写入本次任务回执。

复用凭据存入既有 manifest 的 `lineage`。逐行内容哈希、行数和表结构共同校验三张结果表，不只依赖文件时间或数据行数。常驻 worker 导入后文件变化会拒绝刷新，要求重新启动；运行函数实现也加入指纹，两个新进程的签名稳定性已有测试。部署本次代码后需重新启动相应 worker，首次运行会建立新凭据并完整重建，此后才能复用。

`services/product_category_pnl_read_service.py` 通过只读 repository 调用既有计算器，主服务不再为 YTD 回退导入任务模块。任务模块保留原入口别名。独立冷启动测试禁止加载任务模块和 Dramatiq，实际执行回退并验证数据库文件未变。手工 DELTA 重复累计已经用明确样本复现：两月原始金额 100、200，调整 25，正式结果 325；旧回退返回 350，修复后返回 325。尚未重新物化的新调整不会混进旧 canonical 快照。

性能测量使用本地不可变输入副本，覆盖 2024 年 1 月至 2026 年 8 月，共 32 个月、257,068 行 canonical 和 2,432 行正式视图。改动前代码从本轮编辑前的工作区副本加载，包含当时已有改动；每个场景使用独立数据库和治理目录，串行执行。耗时仅计同步物化调用，包含事务、输入校验和完成回执，不含复制文件及结果比较；属于本机单次对比，不代表生产并发分位数。

| 场景 | 耗时（秒） | 解析月份 | 计算次数 |
| --- | ---: | ---: | ---: |
| 改动前完整刷新 | 49.577 | 32 | 128 |
| 改动后完整刷新 | 41.314 | 32 | 128 |
| 输入无变化刷新 | 2.484 | 0 | 0 |
| 2026 年来源版本变化 | 11.724 | 8 | 32 |

全量刷新用时减少约 16.7%，其中计算阶段从 19.929 秒降至 10.413 秒。无变化刷新较原全量流程减少约 95.0%。单年变化场景只重建 2026 年已有的 8 个月，复用 2024、2025 年；该测量仅改变副本中 2026 年 8 月来源的时间戳，验证保守版本失效，没有改动业务金额。实际金额修订、跨年调整和删除来源另由合成样本测试覆盖。

三组完整比较均通过：改动前完整结果与改动后完整结果、改动后完整结果与无变化刷新、单年重建与相同输入重新完整计算。每组都对三张表执行双向 `EXCEPT ALL`，全部字段及重复行的差异计数均为零，整表 SHA-256 也一致。相同变更输入重新完整计算耗时 41.912 秒，单年重建耗时减少约 72.0%。

原始本地测量回执位于 `.codex-tmp/product-category-core-20260912/`，保留 `before_checked`、`after_full`、`after_noop`、`after_changed`、`after_changed_full` 各目录的 `result.json` 及三份 `compare-*.json`。其中 `measure.py` 固定输入、运行编辑前或编辑后的代码并记录分段耗时，`compare.py` 对三张表执行双向比较。

最后一轮受影响集成测试共 19 个文件、345 项，全部通过，用时 112.98 秒，覆盖账户匹配、增量物化、读取隔离、调整及期间边界、来源解析、接口流程、批量写入、人工参考样本、首页及存储边界。过程中修复了旧流程测试的五处代理函数替换：原测试清理后会残留实例属性，导致后续重载任务时代理引用旧函数；改为准确恢复原实例状态，没有改动任务分发实现。

Ruff 和变更空白检查通过，UTF-8 编码检查没有发现新增损坏。任务、增量状态辅助模块、读取服务及 repository 四个文件的 Mypy 检查通过；对全部六个受影响实现文件运行时，旧核心计算文件仍有 12 处、旧主服务仍有 4 处既存类型错误，本轮没有新增，也没有上调基线。关键检查命令如下；最终集成还包含上述既有接口和首页回归文件。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_product_category_account_matching.py tests/test_product_category_read_boundary.py tests/test_product_category_incremental_materialization.py tests/test_product_category_formula_boundaries.py -q
.\.venv\Scripts\python.exe -m mypy --config-file backend/pyproject.toml --explicit-package-bases --follow-imports=silent backend/app/tasks/product_category_pnl.py backend/app/tasks/product_category_refresh_state.py backend/app/services/product_category_pnl_read_service.py backend/app/repositories/product_category_pnl_repo.py
node scripts/audit_encoding_integrity.mjs
```

这次采用受影响年份重建，思路与 [SQLMesh 的历史重算机制](https://sqlmesh.readthedocs.io/en/stable/concepts/plans/#restatement-plans)一致，但没有引入新调度框架。读取隔离用实际冷启动验证，也吸收了 [Shopify 对模块化检查的复盘](https://shopify.engineering/a-packwerk-retrospective)：静态依赖检查通过还不足以证明模块可以独立运行。

事务内计算、解析或插入失败会回滚；数据库提交后如果治理回执失败，已落地数据不会回滚。任务记录失败，下次保守重建，不能把这一情形描述为数据库与治理存储联合回滚。本轮只操作隔离副本，没有更新正式数据或重启现有服务；其他业务链路仍需各自测量，不能据此宣称全系统性能和计算已完成验收。
