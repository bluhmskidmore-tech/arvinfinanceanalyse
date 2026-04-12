在 `F:\MOSS-V3` 继续执行，不要重做已经完成的回填，直接从当前状态往上层 governed consumers 收口。

开始前先遵守仓库文档优先级，至少阅读：
- `AGENTS.md`
- `prd-moss-agent-analytics-os.md`
- `docs/CODEX_HANDOFF.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/calc_rules.md`
- `docs/data_contracts.md`
- `docs/CACHE_SPEC.md`
- `docs/acceptance_tests.md`

当前已经验证完成的状态：
- `fact_formal_zqtz_balance_daily`：`2024-01-01` 到 `2026-02-28`，`425` 个 distinct `report_date`
- `fact_formal_tyw_balance_daily`：`2025-01-01` 到 `2026-02-28`，`424` 个 distinct `report_date`
- `fact_formal_bond_analytics_daily`：`2024-01-01` 到 `2026-02-28`，`425` 个 distinct `report_date`
- `fact_formal_risk_tensor_daily`：`2024-01-01` 到 `2026-02-28`，`425` 个 distinct `report_date`
- `bond_missing_vs_snapshot = 0`
- `risk_missing_vs_bond = 0`
- `data_input/fx/fx_daily_mid.csv` 已生成并覆盖历史 FX

本轮重要事实：
- `Choice` API 在这台机器上不可用来拉 FX，历史 FX 已通过官方公告生成到 `data_input/fx/fx_daily_mid.csv`
- `ZQTZSHOW-2025.11.20.xls` 存在表内日期漂移，当前 parser 已修成优先使用文件名 `report_date`
- 显式 `ingest_batch_id` 下：
  - 如果某个 family 当天没有 manifest，允许该 family 为空
  - 如果 manifest 存在但 snapshot 缺失，必须 fail closed

执行时不要重复做的事情：
- 不要重跑 `formal_balance_pipeline` 全量历史回填，除非先验证库里覆盖范围已经倒退
- 不要再用 Choice 取 FX
- 不要把 DuckDB 写路径放到 service/api 层

你现在的任务：
1. 验证并补齐更上层 governed consumers 是否已经真正消费到这些历史日期，优先检查：
   - `backend/app/services/balance_analysis_service.py`
   - `backend/app/services/bond_analytics_service.py`
   - `backend/app/services/risk_tensor_service.py`
   - `backend/app/services/executive_service.py`
   - `backend/app/services/agent_service.py`
   - 如相关，再检查 `cube_query_service.py`
2. 对历史日期做应用读面验证，至少包含：
   - 早期样本：`2024-01-01`
   - 中段样本：`2025-11-20`
   - 最新样本：`2026-02-28`
3. 如果上层读面、缓存、refresh 状态或 envelope/result_meta 存在缺口，做最小修复并补测试。
4. 如果发现还有依赖 `bond_analytics` / `risk_tensor` 的 materialize 或 read model 缺口，继续补齐，直到没有剩余日期覆盖缺口。

执行约束：
- 不要回退已有本地修改
- 不要新增依赖
- 只做最小必要修改
- 所有正式金融计算仍必须留在 `backend/app/core_finance/`
- 所有 DuckDB 写入仍必须留在 `backend/app/tasks/`

执行期风险提示：
- 这台机器偶发残留 `python.exe` 子进程，命令行里会带 `--multiprocessing-fork`，会占用 `data/moss.duckdb`
- 如果再次遇到 `duckdb` 文件被占用或 governance 锁超时，先清理这些孤儿进程，再续跑，不要误判成稳定逻辑错误

建议先做的快速核验：
- 读 DuckDB 覆盖范围
- 调用 `bond_analytics_service` / `risk_tensor_service` 的历史日期读面
- 看 `executive_service` / `agent_service` 是否仍只盯着最新日期或旧 fixture

完成标准：
- 上层 governed consumers 对历史日期可读
- 没有新的日期覆盖缺口
- 相关测试通过
- 最终输出：
  - 变更文件列表
  - 新增或修改的测试列表
  - 测试结果
  - 风险点
  - 是否影响正式金融口径
  - 未完成项
  - 下一轮建议
