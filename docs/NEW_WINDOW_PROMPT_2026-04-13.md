在 `F:\MOSS-V3` 继续执行，不要重做已经完成的 benchmark excess 修复，直接从当前工作区状态收口“完整 `pytest` 全绿”。

开始前先遵守仓库文档优先级，至少阅读：
- `AGENTS.md`
- `prd-moss-agent-analytics-os.md`
- `docs/CODEX_HANDOFF.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/calc_rules.md`
- `docs/data_contracts.md`
- `docs/CACHE_SPEC.md`
- `docs/acceptance_tests.md`

当前状态说明：
- 工作区是脏的，已有大量本地修改；不要回退、不要清理、不要重置别人的改动。
- `benchmark_excess` 这一轮已经修到：
  - `portfolio_return` 不再依赖 `benchmark_id`
  - `allocation_effect` 当前显式为 `0`
  - `TREASURY_INDEX / CDB_INDEX / AAA_CREDIT_INDEX` 的 service/core 回归已补齐
- 你需要从这个状态继续，而不是重做这一部分。

你的任务：
1. 先在当前工作区重新运行完整 `pytest`，以当前磁盘状态为准确认剩余失败。
2. 只修“完整 pytest 全绿”所需的最小改动，不扩大范围。
3. 优先处理当前已知的剩余失败簇：
   - `tests/test_agent_enabled_path_smoke.py`
     - 重点看 `duration_risk` / `credit_exposure` 两条，bond analytics seed 与当前 `fact_formal_bond_analytics_daily` schema 漂移。
   - `tests/test_balance_analysis_consumer_surface.py`
     - `cashflow_projection_service.py` 不应直接导入 `BalanceAnalysisRepository`。
   - `tests/test_yield_curve_materialize.py`
     - `test_materialize_yield_curve_unsupported_curve_type_fails_closed` 在全量顺序下有异常类身份漂移问题。
4. 每修一簇先跑对应定向测试，再回到完整 `pytest`。
5. 直到完整 `pytest` 全绿再停止。

执行约束：
- 不要新增依赖。
- 不要把正式金融计算移出 `backend/app/core_finance/`。
- 不要把 DuckDB 写路径放进 service/api。
- 不要为了过测试而回退 benchmark excess 的当前实现口径。
- 如果需要改测试，只能改那些已经与当前真实 schema/contract 漂移的测试，不要用“放宽断言”掩盖真实 bug。

建议顺序：
1. 跑完整 `pytest`
2. 修 agent smoke seed / contract 漂移
3. 修 cashflow projection consumer surface
4. 修 yield curve fail-closed 测试稳定性
5. 再跑完整 `pytest`

完成标准：
- `pytest -q F:\MOSS-V3` 全部通过
- 没有新增失败
- 不破坏 benchmark excess 已补齐的回归

最终输出必须包含：
- 变更文件列表
- 新增或修改的测试列表
- 测试结果
- 风险点
- 是否影响正式金融口径
- 未完成项
- 下一轮建议

如果你遇到和当前工作区脏状态冲突的文件，不要强行覆盖，先读取并基于现状最小修改。
