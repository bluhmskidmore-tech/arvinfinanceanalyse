本轮确认产品损益刷新存在逐行写库开销，已将事实表插入调整为最多 500 行一批。改动位于 `backend/app/tasks/product_category_pnl.py`，仍使用原来的单次刷新事务、Decimal 参数、来源版本和重算范围。金融公式、数据库结构、权限、队列及正式数据库均未改动。

验收日期为 2026-09-11。基线取本轮开始时的工作区版本，保留已有未提交改动；Git HEAD 为 `3ca0bbc438644214878bd789c4322a722c9d6393`，Python 环境使用项目 `.venv`，DuckDB 版本为 1.5.1。输入文件与人工调整记录复制到本地隔离目录，各次回放分别写入独立的 DuckDB 和治理回执目录。原始材料未发送至外部服务。

输入快照包含 32 对总账与日均文件，覆盖 2024-01 至 2026-08。目录中另一份财务指标工作簿不属于产品损益解析入口。固定来源内容、文件时间和 FTP 配置后，分别运行改动前、改动后的完整刷新。

| 实测项目 | 改动前 | 改动后 |
| --- | ---: | ---: |
| 来源月份 | 32 | 32 |
| 事实表行数 | 257,068 | 257,068 |
| 正式展示表行数 | 2,432 | 2,432 |
| 情景表行数 | 0 | 0 |
| 带 cProfile 的总耗时（秒） | 203.270 | 165.273 |
| cProfile 中数据库 execute 调用次数 | 259,909 | 3,372 |
| 数据库 execute 调用累计耗时（秒） | 89.435 | 22.463 |
| 关闭 cProfile 后总耗时（秒） | 188.121 | 65.219 |

每个版本各进行一次带分析器、一次关闭分析器的回放。分析器用于定位开销，关闭分析器的回放用于观察完整任务耗时；这些是本机单次测量，尚未建立固定负载下的分位数基线。任务计时覆盖建表、解析、计算、写库和治理回执，不含 Python 进程启动及输入复制。

四次完整回放已核对三张表全部字段的排序序列 SHA-256，并完成双向 `EXCEPT ALL` 比较，所有差异行数均为 0，日期、规则版本及来源版本也一致。关闭分析器的本次前后回放耗时减少约 65.3%。新增的 `tests/test_product_category_materialization_batches.py` 覆盖 1,001 行跨批次精确保存、空事实集、重复刷新不重复计数，以及最后一批数值溢出时回滚并恢复三张原有表。该测试使用合成输入，独立检查八位小数、大额正负数与最小小数单位；它检验存储行为。

本轮函数影响分析使用当前工作树对应的 GitNexus 索引，静态风险评级为 LOW，直接调用者为同步包装函数。结合当前代码补查，后台 actor 与同步刷新服务都会进入这段逻辑，均保留原入口和事务。当前补丁未扩大到其他任务。

本地实验脚本、输入指纹、任务改动前副本、各次结果和性能分析文件保留在 `.codex-tmp/product-category-baseline-20260911/`。`measure.py` 固定复用已有输入快照，每个新标签创建独立输出目录；重复标签会拒绝覆盖。`verify_outputs.py` 通过双向 `EXCEPT ALL` 检查四次回放的所有字段及重复行数量，并写入 `comparison.json`。

验证命令如下，须在项目根目录使用项目 Python。性能实验应串行运行，避免同时运行测试影响耗时。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_product_category_materialization_batches.py tests/test_product_category_pnl_flow.py tests/test_product_category_period_adjustment_boundaries.py tests/test_product_category_source_period.py -q --durations=5
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml backend/app/tasks/product_category_pnl.py tests/test_product_category_materialization_batches.py
.\.venv\Scripts\python.exe -m mypy --config-file backend/pyproject.toml --follow-imports=skip --ignore-missing-imports backend/app/tasks/product_category_pnl.py
.\.venv\Scripts\python.exe .codex-tmp/product-category-baseline-20260911/verify_outputs.py
node scripts/audit_encoding_integrity.mjs
```

测试收口结果：上述四个测试文件共 94 项通过，耗时 86.43 秒；Ruff 通过；限定任务文件的 Mypy 检查通过；四次回放的三张表双向差异均为 0；编码检查扫描 4,432 个文件，未发现新增损坏。`git diff --check` 对本轮涉及路径通过。本轮新增三项批次检查，并复用现有期间、人工调整、读取接口和来源日期测试。

这次修复参考了 DuckDB 官方关于[批量导入](https://duckdb.org/docs/current/clients/python/data_ingestion)和 [Python DB API](https://duckdb.org/docs/current/clients/python/dbapi) 的说明。官方提醒大量数据不宜使用 `executemany`。本地 6,000 行合成数据对照中，逐行执行为 2.244 秒，`executemany` 为 1.634 秒，500 行多值参数插入为 0.340 秒，三种方式结果一致；据此选择了无需新增依赖、继续逐个绑定 Decimal 参数的局部改法。

下一轮应先补齐一个业务认可的独立金额对照样本，再处理计算阶段的重复账户匹配。本轮分析中 `_matches_account` 调用了约 8,499 万次；后续优化须沿用当前结果对照，并覆盖科目前缀、币种及期间累计边界。缩小历史重算范围还需要明确历史来源修订、人工调整变更对后续月份的影响。

独立业务金额对账与网页版 Pro 复核均为 PENDING。当前用户已选择先完成本地执行与验证，Pro 恢复后再补复核。本轮全量结果一致只能证明本次写库优化保留现有结果；正式业务口径的独立正确性仍由单独对账确认。
