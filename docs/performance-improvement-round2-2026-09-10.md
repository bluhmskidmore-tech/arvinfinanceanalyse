# 页面响应优化第二轮验收

同日晚间按用户要求再次实测，捕获一次连接中断，并发现 2026-07-31 历史查询仍耗时 55.125 秒；恢复后 90 次固定日期请求全部成功。下文保留本轮早先的真实采样，当前验收限制以[晚间复测报告](F:/MOSS-V3/docs/performance-retest-2026-09-10.md)为准。

2026-09-10。第二轮后端优化已在日常使用的本机系统生效，两个过期比较期已通过现有请求与后台任务链路补齐。实际 7888 接口连续读取 30 次，中位耗时 1.904 秒、P95 为 2.067 秒，全部成功且与原始业务基线一致。5888 页面已实际打开并显示 2026-08-31 的正式结构分析。全系统一秒返回和后台重算期间连续读取仍未通过验收。

本轮沿用用户授权的子代理分工：后端由 gpt-5.6-sol 实施，前端发布核查由 gpt-5.6-terra 负责，运维入口和独立审查由 gpt-5.6-luna 负责。主代理执行真实数据对比、接口采样、任务提交、服务恢复与最终验收。工作区既有未提交改动被保留，没有提交 Git。

剩余耗时主要来自追溯检查中的相关子查询，以及同一洞察请求对相同来源反复扫描。`pnl_repo.py` 将指定日期的匹配改为预筛选、匹配代码展开与等值连接聚合，完整保留严格和宽松匹配条件、重复损益行以及空值语义。`pnl_service.py` 和洞察组合服务只在单次请求内复用完整来源版本，键包含数据库路径、年度、截止日、规范化 FTP 和手工调整版本。每个预计算载荷仍单独核对规则及内容，没有增加跨请求 TTL。

GitNexus 对本轮相关符号报告 LOW；主代理与子代理通过局部调用搜索补足索引未返回的洞察 API、预计算任务和契约测试调用。未改变金融公式、数据库结构或用户权限。

| 验收场景 | 结果 |
| --- | --- |
| 真实库 21 个日期的新旧追溯结果 | 全部一致 |
| 真实库追溯查询，单次旧版 / 新版 | 1.317 / 0.143 秒 |
| 同一隔离数据，上一轮 / 本轮 HTTP P95，各 30 次 | 2.887 / 1.448 秒 |
| 实际 7888 接口 30 次 P50 / P95 / 最大值 | 1.904 / 2.067 / 2.205 秒 |
| 实际接口 5 个同时请求，单批最小 / 最大值 | 1.288 / 1.805 秒 |
| 实际接口的 30 次顺序和 5 次同时请求 | 35 次成功、0 处结果差异 |
| 首页、市场、产品分类、余额、风险读取 | 切换前后均为 200，结果摘要一致 |

隔离比较覆盖业务结果、组件证据和结果元数据，只排除每次生成的时间与 trace。实际 HTTP 比较沿用原始响应经既有 `ResultEnvelope` 序列化后的完整基线，包括默认字段。5 个同时请求仅为一次并发检查，不能推导系统容量、不同日期混合负载或持续高并发的 P95。

真实库的两个比较期原来各有 118 条记录，但规则版本为 v14，读取要求为 v17。用户明确授权本机运维仅补齐 2025-08-31 和 2025-12-31 后，主代理调用既有 `request_pnl_by_business_precompute_rebuild(..., scope="selected")`，由既有 Redis Dramatiq worker 执行，保留 queued、running 和 completed 回执。两个日期串行提交，没有重建整年历史，也没有重跑余额或产品分类损益。

| 比较截止日 | Run ID | 执行耗时 | 记录数 | 最终状态 |
| --- | --- | --- | --- | --- |
| 2025-08-31 | `pnl_by_business_precompute:7aa83026-5209-4437-bbb5-e13f0ea3fb0f` | 47.312 秒 | 118 | completed / v17 / current |
| 2025-12-31 | `pnl_by_business_precompute:680c7513-7d02-46c8-b51d-a5f63618e7f5` | 72.219 秒 | 118 | completed / v17 / current |

补算前已备份这两个预计算分区，文件为 733,279 字节；原始金融事实没有作为本次写入目标。本机 API 与 worker 的 Redis 客户端经连接端口核对实际使用 DB11，当时没有待执行或运行中的消息，只有一条历史失败消息。本次为规避 DuckDB 进程间读写锁冲突使用了维护窗口，暂时停止 API 和自动恢复进程，并暂停数据更新队列定时任务。结束时已恢复 API、worker、keepalive 和 `MOSS-DataUpdateQueue`，`/health`、`/health/ready`、前端构建探测全部通过，没有遗留 maintenance 标记或 DuckDB WAL。

实际页面保留正式使用、日期、降级和质量披露。现有的 `quality=warning` 及 2025-11-20 余额来源待核实提示仍然存在；结果一致不等于这项历史数据质量问题已经解决。

前端本轮没有整体发布。运行包的原清单与实际入口不一致，主代理已将当前 593 个文件逐字节复制成可回退包，重新生成完整清单并通过既有运行控制器校验。实际页面内容保持原版本。当前完整源码包含产品分类的在途改动，扩大回归时已捕获净收益符号测试 1 项失败、正式历史测试 5 项失败，因此候选构建暂停；后续 typecheck、lint、debt audit、完整构建均未宣称通过。上一轮前端刷新状态与取消请求改动仍需在可发布的前端版本中完成验收后切换。

本轮生产代码改动为下列三个文件，另更新四份相关测试中的边界用例和可选参数夹具：

- [pnl_repo.py](F:/MOSS-V3/backend/app/repositories/pnl_repo.py)
- [pnl_service.py](F:/MOSS-V3/backend/app/services/pnl_service.py)
- [pnl_by_business_candidate_insights.py](F:/MOSS-V3/backend/app/services/pnl_by_business_candidate_insights.py)
- [test_pnl_by_business_candidate_insights_contract.py](F:/MOSS-V3/tests/test_pnl_by_business_candidate_insights_contract.py)
- [test_pnl_by_business_precompute_ftp_parity.py](F:/MOSS-V3/tests/test_pnl_by_business_precompute_ftp_parity.py)
- [test_pnl_by_business_insights_contract.py](F:/MOSS-V3/tests/test_pnl_by_business_insights_contract.py)
- [test_pnl_api_contract.py](F:/MOSS-V3/tests/test_pnl_api_contract.py)

后端定向测试 65 项通过，主代理扩大接口回归后发现并修复了新增可选参数与旧测试夹具不兼容的问题，最终接口及正式洞察回归 79 项通过，原有业务及正式准入断言保留。合计 144 项。相关 Ruff、差异空白和 UTF-8 检查通过；`pnl_service.py` 完整 Ruff 仍有基线既存的 9 个 F401，忽略这组既有导入问题后通过，没有清理其他任务的导入。

```text
.venv/Scripts/python.exe -m pytest tests/test_pnl_by_business_candidate_insights_contract.py -q
16 passed

.venv/Scripts/python.exe -m pytest tests/test_pnl_by_business_precompute_ftp_parity.py -q
38 passed

.venv/Scripts/python.exe -m pytest tests/test_pnl_insights_performance_dependencies.py -q
11 passed

.venv/Scripts/python.exe -m pytest tests/test_pnl_by_business_insights_contract.py tests/test_pnl_api_contract.py -k "insights or precompute or materialize" -q
79 passed, 125 deselected

.venv/Scripts/python.exe scripts/dev_runtime_control.py frontend-probe
passed
```

基线、补丁、来源副本核对、接口原始采样、运维授权记录、分区备份和三阶段回执保留在 [第二轮验收目录](F:/MOSS-V3/.codex-tmp/performance-round2-20260910)。其中 `production-insights-http-30-samples.json` 为实际系统延迟，`production-read-parity.json` 为五类读取对比，`runtime-operation.json` 记录恢复状态与源码指纹。`rollback-dist` 是已登记的运行恢复包，应保留。隔离数据库在验收结束后清理，比较结果和构建回退包保留。
