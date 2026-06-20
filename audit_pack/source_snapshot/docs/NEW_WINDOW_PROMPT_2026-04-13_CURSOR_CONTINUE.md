在 `F:\MOSS-V3` 继续执行，不要重做已经完成的 review 修复，直接从当前工作区状态收口“完整 `pytest` 全绿”。

开始前先遵守仓库文档优先级，至少阅读：
- `AGENTS.md`
- `prd-moss-agent-analytics-os.md`
- `docs/DOCUMENT_AUTHORITY.md`
- `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`
- `docs/calc_rules.md`
- `docs/data_contracts.md`
- `docs/CACHE_SPEC.md`
- `docs/acceptance_tests.md`

如需 repo 历史背景或 phase 计划上下文，再按需查 `docs/CODEX_HANDOFF.md`、`docs/IMPLEMENTATION_PLAN.md`，不要把它们当作当前状态入口。

当前已知前置状态：
- `benchmark_excess` 这轮修复已经在当前工作区落地，不要回退：
  - `portfolio_return` 不再依赖 `benchmark_id`
  - `allocation_effect` 当前显式为 `0`
  - `TREASURY_INDEX / CDB_INDEX / AAA_CREDIT_INDEX` 的 service/core 回归已补齐
- review 提到的 `tests/test_ingest_foundation.py` 的 P1 模块泄漏问题已经在当前工作区修完：
  - 用 `importlib.import_module("backend.app.governance.settings")`
  - 在 `finally` 里同时清掉 `backend.app.tasks.ingest` 和 `backend.app.tasks.broker`
- 不要重做这两部分，只从当前磁盘状态往下继续。

你的任务：
1. 先重新运行完整 `pytest`，以当前磁盘状态为准确认剩余失败。
2. 只修“完整 pytest 全绿”所需的最小改动，不扩大范围。
3. 当前优先关注仍可能残留的失败簇，但以最新实跑结果为准：
   - `tests/test_agent_enabled_path_smoke.py`
   - `tests/test_balance_analysis_consumer_surface.py`
   - `tests/test_yield_curve_materialize.py`
   - 以及任何因模块缓存 / `load_module` 与 `importlib.import_module` 混用导致的顺序相关失败
4. 每修一簇先跑对应定向测试，再回到完整 `pytest`。
5. 直到 `pytest -q F:\MOSS-V3` 全绿再停止。

执行约束：
- 不要新增依赖。
- 不要回退当前工作区已有本地修改。
- 不要用 `git reset --hard`、`git checkout --` 等破坏性命令。
- 不要把正式金融计算移出 `backend/app/core_finance/`。
- 不要把 DuckDB 写路径放进 service/api。
- 不要为了过测试而回退 benchmark excess 的当前实现口径。
- 如果需要改测试，只能改那些已经与当前真实 schema/contract 漂移、或存在明显模块缓存/模块身份问题的测试；不要用放宽断言掩盖真实 bug。

建议顺序：
1. 跑完整 `pytest`
2. 记录首个失败簇
3. 定向修复 + 定向回归
4. 再跑完整 `pytest`
5. 重复直到全绿

建议命令：
- `pytest -q F:\MOSS-V3`
- 若输出被截断，可用 Python 包一层把日志写到文件，再读尾部：
  - 用 `python -` 调 `pytest.main([r'F:\\MOSS-V3'])`
  - 将 stdout/stderr 重定向到仓库内日志文件

完成标准：
- `pytest -q F:\MOSS-V3` 全部通过
- 没有新增失败
- 不破坏 benchmark excess 与 ingest review 修复

最终输出必须包含：
- 变更文件列表
- 新增或修改的测试列表
- 测试结果
- 风险点
- 是否影响正式金融口径
- 未完成项
- 下一轮建议

如果你遇到和当前工作区脏状态冲突的文件，不要强行覆盖，先读取并基于现状最小修改。
